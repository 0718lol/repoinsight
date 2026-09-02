"""Call graph: resolve raw call names inside functions to definitions."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .models import Import, Symbol


class CallGraph:
    """Resolves call sites to symbol definitions using imports and scope."""

    def __init__(self, symbols: List[Symbol], imports: List[Import]):
        self.symbols = symbols
        # qualified name -> Symbol
        self.by_qualified: Dict[str, Symbol] = {s.qualified_name: s for s in symbols}
        # simple name -> set of qualified names (overloads across classes etc.)
        self.by_name: Dict[str, Set[str]] = defaultdict(set)
        for s in symbols:
            if s.is_function_like:
                self.by_name[s.name].add(s.qualified_name)

        # module of each symbol, derived from file path
        self.module_of_symbol: Dict[str, str] = {}
        for s in symbols:
            self.module_of_symbol[s.qualified_name] = _file_to_module(s.file)

        # module -> set of imported (alias, full target) pairs
        self.imported_names: Dict[str, Dict[str, str]] = defaultdict(dict)
        for imp in imports:
            mod = _file_to_module(imp.file)
            if imp.is_relative:
                continue  # handled via name match below
            for name in imp.names:
                if name == "*":
                    continue
                alias = name
                self.imported_names[mod].setdefault(alias, f"{imp.module}.{name}" if imp.module else name)

        # call edges: caller qualified -> callee qualified
        self.edges: Dict[str, Set[str]] = defaultdict(set)

    # ------------------------------------------------------------------ #
    def resolve_call(self, caller: Symbol, raw: str) -> Optional[str]:
        """Resolve a raw call name to a qualified symbol, when possible."""
        # 1. Imported names: "from pkg.mod import helper" then helper(...)
        module = self.module_of_symbol.get(caller.qualified_name, "")
        target = self.imported_names.get(module, {}).get(raw)
        if target and target in self.by_qualified:
            return target
        if "." in raw:
            head, rest = raw.split(".", 1)
            # dotted import like "mod.helper()" imported as "import pkg.mod"
            head_target = self.imported_names.get(module, {}).get(head)
            if head_target:
                candidate = f"{head_target}.{rest}"
                if candidate in self.by_qualified:
                    return candidate
            # 2. typed local variable: cart = Cart(); cart.add(...)
            cls_name = (caller.var_types or {}).get(head)
            if cls_name:
                class_q = self._find_class(module, cls_name)
                if class_q:
                    resolved = self._method_on_class(class_q, rest)
                    if resolved:
                        return resolved
            # 3. method call inside the same class: self.method(...),
            #    walking up the inheritance chain when needed
            if raw.startswith(("self.", "this.", "super.")) and caller.parent:
                resolved = self._method_on_class(caller.parent, rest)
                if resolved:
                    return resolved
        # 4. Same-scope simple name (sibling function in module or class).
        if raw in self.by_name:
            candidates = self.by_name[raw]
            # prefer a sibling in the same parent scope, else same module
            same_parent = [c for c in candidates
                           if self.by_qualified[c].parent == caller.parent]
            if same_parent:
                return sorted(same_parent)[0]
            same_module = [c for c in candidates
                           if self.module_of_symbol[c] == module]
            if same_module:
                return sorted(same_module)[0]
            return sorted(candidates)[0]
        return None

    # ------------------------------------------------------------------ #
    def _find_class(self, module: str, simple_name: str) -> Optional[str]:
        """Locate a class by simple name: same module first, then imports."""
        candidate = f"{module}.{simple_name}"
        if candidate in self.by_qualified:
            return candidate
        imported = self.imported_names.get(module, {}).get(simple_name)
        if imported and imported in self.by_qualified:
            return imported
        return None

    def _method_on_class(self, class_q: str, rest: str, depth: int = 0) -> Optional[str]:
        """Resolve `rest` as a method/attribute path on class_q, walking
        base classes up to a few levels for inherited methods."""
        if depth > 4:
            return None
        candidate = f"{class_q}.{rest}"
        if candidate in self.by_qualified:
            return candidate
        cls_sym = self.by_qualified.get(class_q)
        if cls_sym is None or cls_sym.kind != "class":
            return None
        module = self.module_of_symbol.get(class_q, "")
        for base in cls_sym.bases:
            simple = base.split(".")[-1]
            base_q = self._find_class(module, simple)
            if base_q:
                resolved = self._method_on_class(base_q, rest, depth + 1)
                if resolved:
                    return resolved
        return None

    # ------------------------------------------------------------------ #
    def build(self) -> Dict[str, Set[str]]:
        for sym in self.symbols:
            if not sym.is_function_like:
                continue
            for raw in sym.calls:
                resolved = self.resolve_call(sym, raw)
                if resolved and resolved != sym.qualified_name:
                    self.edges[sym.qualified_name].add(resolved)
        return self.edges

    # ------------------------------------------------------------------ #
    def callers_of(self, qualified_name: str) -> List[str]:
        return sorted(c for c, callees in self.edges.items() if qualified_name in callees)

    def callees_of(self, qualified_name: str) -> List[str]:
        return sorted(self.edges.get(qualified_name, ()))

    def to_edge_list(self) -> List[Tuple[str, str]]:
        return sorted(
            (caller, callee)
            for caller, callees in self.edges.items()
            for callee in callees
        )


def _file_to_module(rel_path: str) -> str:
    from .module_graph import file_to_module
    return file_to_module(rel_path)
