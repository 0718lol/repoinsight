"""JavaScript parser built on an optional tree-sitter backend."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import List, Optional

from ..models import Import, Symbol

_BRANCH_NODES = {
    "if_statement",
    "for_statement",
    "for_in_statement",
    "for_of_statement",
    "while_statement",
    "catch_clause",
    "switch_case",
    "conditional_expression",
}


def _node_text(source: bytes, node) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _node_kind(node) -> Optional[str]:
    if node.type == "class_declaration":
        return "class"
    if node.type == "function_declaration":
        return "async_function" if any(child.type == "async" for child in node.children) else "function"
    if node.type == "method_definition":
        return "async_function" if any(child.type == "async" for child in node.children) else "function"
    return None


def _decl_name(node) -> str:
    name = node.child_by_field_name("name")
    if name is not None:
        return name.text.decode("utf-8", errors="replace")
    return ""


class JavaScriptParser:
    """Parse one JavaScript file into Symbol and Import records."""

    def __init__(self, rel_path: str):
        self.rel_path = rel_path
        self.symbols: List[Symbol] = []
        self.imports: List[Import] = []
        self._scope_kinds: dict = {}
        self._source = b""

    # ------------------------------------------------------------------ #
    def parse(self, source: str) -> None:
        parser = _load_parser()
        self._source = source.encode("utf-8", errors="replace")
        tree = parser.parse(self._source)
        if getattr(tree.root_node, "has_error", False):
            raise ValueError("syntax error: tree-sitter reported parse errors")
        self._walk(tree.root_node, prefix=None)

    # ------------------------------------------------------------------ #
    def _walk(self, node, prefix: Optional[str]) -> None:
        for child in node.named_children:
            if child.type == "import_statement":
                self._collect_import(child)
                continue
            if child.type == "export_statement":
                self._walk(child, prefix)
                continue

            kind = _node_kind(child)
            if kind is None:
                self._walk(child, prefix)
                continue

            name = _decl_name(child)
            if not name:
                self._walk(child, prefix)
                continue

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
                line_start=child.start_point[0] + 1,
                line_end=child.end_point[0] + 1,
                parent=prefix,
            )

            if child.type == "class_declaration":
                sym.bases = self._collect_bases(child)
            else:
                sym.calls, sym.complexity = self._scan_body(child)

            self.symbols.append(sym)
            self._scope_kinds[qualified] = kind
            self._walk(child, prefix=qualified)

    # ------------------------------------------------------------------ #
    def _scan_body(self, node) -> "tuple[List[str], int]":
        calls: List[str] = []
        branches = 0
        stack = [node]
        while stack:
            current = stack.pop()
            for child in current.named_children:
                if child.type == "call_expression":
                    callee = child.child_by_field_name("function")
                    if callee is not None:
                        raw = _node_text(self._source, callee)
                        if raw:
                            calls.append(raw)
                if child.type in _BRANCH_NODES:
                    branches += 1
                elif child.type == "binary_expression":
                    op = self._binary_operator(child)
                    if op in {"&&", "||", "??"}:
                        branches += 1
                stack.append(child)
        return calls, 1 + branches

    def _binary_operator(self, node) -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None:
            return ""
        left_end = left.end_byte
        right_start = right.start_byte
        gap = self._source[left_end:right_start].decode("utf-8", errors="replace").strip()
        return gap

    def _collect_bases(self, node) -> List[str]:
        superclass = node.child_by_field_name("superclass")
        if superclass is None:
            return []
        return [_node_text(self._source, superclass)]

    def _collect_import(self, node) -> None:
        text = _node_text(self._source, node)
        module_match = re.search(r"from\s+['\"]([^'\"]+)['\"]", text)
        module = module_match.group(1) if module_match else ""
        names: List[str] = []
        clause = text.split("import ", 1)[1]
        if not module and clause.strip().startswith(("'", '"')):
            module = clause.strip().strip(";").strip("'\"")
            names = ["*"]
            self.imports.append(
                Import(
                    file=self.rel_path,
                    module=module,
                    names=names,
                    line=node.start_point[0] + 1,
                    is_relative=False,
                    level=0,
                )
            )
            return
        if " from " in clause:
            clause = clause.split(" from ", 1)[0].strip()
        if clause.startswith("* as "):
            alias = clause[5:].strip()
            if alias:
                names = [alias]
        else:
            if "," in clause:
                head, tail = clause.split(",", 1)
                head = head.strip()
                tail = tail.strip()
            else:
                head, tail = clause.strip(), ""
            if head and not head.startswith("{"):
                names.append(head)
            if tail.startswith("{") and tail.endswith("}"):
                inner = tail[1:-1]
            elif head.startswith("{") and head.endswith("}"):
                inner = head[1:-1]
                names = []
            else:
                inner = ""
            for item in inner.split(","):
                item = item.strip()
                if not item:
                    continue
                if " as " in item:
                    names.append(item.split(" as ", 1)[1].strip())
                else:
                    names.append(item)
        if not names:
            names = ["*"]
        self.imports.append(
            Import(
                file=self.rel_path,
                module=module,
                names=names,
                line=node.start_point[0] + 1,
                is_relative=False,
                level=0,
            )
        )


def _load_parser():
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError:
        try:
            from tree_sitter_languages import get_parser
        except ImportError as exc:
            raise RuntimeError(
                "JavaScript analysis requires tree-sitter support; "
                "install repoinsight[js] to enable it."
            ) from exc
    return get_parser("javascript")


@lru_cache(maxsize=1)
def javascript_backend_available() -> bool:
    try:
        _load_parser()
    except Exception:
        return False
    return True
