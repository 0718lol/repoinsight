"""Python AST parser: extracts symbols, imports and call sites."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional

from ..models import Import, Symbol

# Statement types that each add one branch to cyclomatic complexity.
_BRANCH_NODES = (
    ast.If, ast.For, ast.While, ast.IfExp,
    ast.ExceptHandler, ast.With, ast.Assert, ast.comprehension,
)


def _node_kind(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.AsyncFunctionDef):
        return "async_function"
    if isinstance(node, ast.FunctionDef):
        return "function"
    if isinstance(node, ast.ClassDef):
        return "class"
    return None


def _name_of(node: ast.AST) -> str:
    """Best-effort dotted name for a call target or attribute chain."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name_of(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _name_of(node.func)
    return ""


def _annotation_name(node: Optional[ast.AST]) -> str:
    return _name_of(node) if node is not None else ""


class PythonParser:
    """Parse one Python file into Symbol and Import records."""

    def __init__(self, rel_path: str):
        self.rel_path = rel_path
        self.symbols: List[Symbol] = []
        self.imports: List[Import] = []
        self._scope_kinds: dict = {}   # qualified scope name -> "class"/"function"/...

    # ------------------------------------------------------------------ #
    def parse(self, source: str) -> None:
        try:
            tree = ast.parse(source, filename=self.rel_path)
        except SyntaxError as exc:
            raise ValueError(f"syntax error: {exc}") from exc
        self._walk(tree, prefix=None)

    # ------------------------------------------------------------------ #
    def _walk(self, node: ast.AST, prefix: Optional[str]) -> None:
        """Depth-first walk. `prefix` is the dotted scope path built so far
        (file-relative); nested defs extend it, so a method inside a
        module-level class gets qualified "Class.method"."""
        for child in ast.iter_child_nodes(node):
            kind = _node_kind(child)
            if kind is None:
                # Statements at module/class level may still hold imports.
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    self._collect_import(child)
                self._walk(child, prefix)
                continue

            name = child.name
            qualified = f"{prefix}.{name}" if prefix else name

            if kind in ("function", "async_function") and prefix:
                enclosing = self._scope_kinds.get(prefix)
                if enclosing == "class" and kind == "function":
                    kind = "method"

            sym = Symbol(
                kind=kind,
                name=name,
                qualified_name=qualified,
                file=self.rel_path,
                line_start=child.lineno,
                line_end=getattr(child, "end_lineno", child.lineno) or child.lineno,
                parent=prefix,
            )

            if isinstance(child, ast.ClassDef):
                sym.bases = [_name_of(b) for b in child.bases]
                self._collect_class_imports(child)
            else:
                sym.decorators = [_name_of(d) for d in child.decorator_list]
                body_calls, branch_count, var_types = self._scan_body(child)
                sym.calls = body_calls
                sym.complexity = 1 + branch_count
                sym.var_types = var_types

            self.symbols.append(sym)
            self._scope_kinds[qualified] = kind
            self._walk(child, prefix=qualified)

    # ------------------------------------------------------------------ #
    def _scan_body(self, func: ast.AST) -> "tuple[List[str], int, dict]":
        """Collect call names, branches and local variable type hints."""
        calls: List[str] = []
        branches = 0
        var_types: dict = {}
        stack = [getattr(func, "body", [])]
        while stack:
            for stmt in stack.pop():
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Call):
                        target = _name_of(sub.func)
                        if target:
                            calls.append(target)
                    if isinstance(sub, _BRANCH_NODES):
                        branches += 1
                    elif isinstance(sub, ast.BoolOp):
                        branches += max(0, len(sub.values) - 1)
                    elif isinstance(sub, ast.Assign) and len(sub.targets) == 1:
                        self._record_assign(sub.targets[0], sub.value, var_types)
                    elif isinstance(sub, ast.AnnAssign) and sub.value is not None:
                        self._record_assign(sub.target, sub.value, var_types,
                                            annotation=sub.annotation)
        return calls, branches, var_types

    def _record_assign(self, target: ast.AST, value: ast.AST,
                       var_types: dict, annotation: ast.AST = None) -> None:
        """Track simple cases: `x: ClassName = ...` always, and `x = Name(...)`
        only when the name looks like a class (uppercase first letter), so
        factory functions like `make()` are not mistaken for constructors."""
        if not isinstance(target, ast.Name):
            return
        if annotation is not None:
            cls = _name_of(annotation)
            if cls and "." not in cls:
                var_types[target.id] = cls
            return
        if isinstance(value, ast.Call):
            cls = _name_of(value.func)
            if cls and "." not in cls and cls[:1].isupper():
                var_types[target.id] = cls

    # ------------------------------------------------------------------ #
    def _collect_class_imports(self, cls: ast.ClassDef) -> None:
        for stmt in cls.body:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                self._collect_import(stmt)

    def _collect_import(self, node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                self.imports.append(
                    Import(
                        file=self.rel_path,
                        module=alias.name,
                        names=[alias.asname or alias.name.split(".")[0]],
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level = node.level or 0
            names = [a.name for a in node.names]
            self.imports.append(
                Import(
                    file=self.rel_path,
                    module=module,
                    names=["*"] if "*" in names else names,
                    line=node.lineno,
                    is_relative=level > 0,
                    level=level,
                )
            )


def parse_python_file(path: Path, rel_path: str) -> "tuple[List[Symbol], List[Import]]":
    """Convenience wrapper: parse a file from disk."""
    parser = PythonParser(rel_path)
    source = path.read_text(encoding="utf-8", errors="replace")
    parser.parse(source)
    return parser.symbols, parser.imports
