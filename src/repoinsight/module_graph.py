"""Module graph: map files to dotted module names, resolve imports, build edges."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Dict, List, Optional, Set

from .models import Import, SourceFile


def module_name_for(rel_path: str) -> str:
    """Convert 'pkg/sub/mod.py' -> 'pkg.sub.mod'; '__init__.py' -> 'pkg.sub'.

    Non-python files keep posix path with the suffix stripped: 'docs/x.md'
    -> 'docs/x'.
    """
    p = PurePosixPath(rel_path)
    parts = list(p.parts)
    if p.suffix == ".py":
        parts[-1] = p.stem
        if parts[-1] == "__init__":
            parts = parts[:-1] or ["__root__"]
        return ".".join(parts)
    parts[-1] = p.stem
    return "/".join(parts)


def file_to_module(rel_path: str) -> str:
    """Inverse mapping of module_name_for for files: used to qualify symbols.

    'pkg/mod.py' -> 'pkg.mod'; '__init__.py' at root -> '__root__'.
    """
    parts = rel_path.replace("\\", "/").split("/")
    if parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1] or ["__root__"]
    return ".".join(parts)


# Legacy alias used across the codebase.
_file_to_module = file_to_module


class ModuleGraph:
    """Resolves imports between files of a single repository."""

    def __init__(self, files: List[SourceFile]):
        self.root: str = ""
        self.file_by_module: Dict[str, str] = {}
        self.modules_by_top: Dict[str, List[str]] = {}
        self.package_dirs: Set[str] = set()
        for f in files:
            mod = module_name_for(f.path)
            if f.path.endswith("__init__.py") and mod != "__root__":
                parts = f.path.split("/")
                self.package_dirs.add("/".join(parts[:-1]))
            self.file_by_module[mod] = f.path
            top = mod.split(".")[0]
            self.modules_by_top.setdefault(top, []).append(mod)

    # ------------------------------------------------------------------ #
    def resolve_import(self, imp: Import) -> Optional[str]:
        """Resolve an import to a local module name, or None if external.

        For 'from X import y' we prefer the most specific local target:
        try 'X.y' first (y may be a submodule), then 'X'.
        """
        if imp.is_relative:
            target = self._resolve_relative(imp)
        else:
            target = self._resolve_absolute(imp.module)
        if target is None:
            return None
        if not imp.is_relative and imp.module:
            for name in imp.names:
                if name == "*":
                    continue
                candidate = f"{target}.{name}"
                if candidate in self.file_by_module:
                    return candidate
        return target

    def _resolve_absolute(self, module: str) -> Optional[str]:
        parts = module.split(".")
        # Try the longest prefix that exists as a module.
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in self.file_by_module:
                return candidate
            # Package directory (only its __init__ matched a module above).
            rel = "/".join(parts[:i])
            if rel in self.package_dirs:
                return candidate
        return None

    def _resolve_relative(self, imp: Import) -> Optional[str]:
        imp_mod_path = PurePosixPath(imp.file)
        if imp.file.endswith("__init__.py"):
            base_parts = list(imp_mod_path.parts[:-1])
        else:
            base_parts = list(imp_mod_path.parts[:-1])
        # ast ImportFrom.level: 1 dot -> current package, 2 dots -> parent, ...
        # For a module file, one dot refers to its containing package.
        dots = max(1, imp.level)
        # The importing module's own package is base_parts; each extra dot
        # climbs one package level.
        base_parts = base_parts[: len(base_parts) - (dots - 1)] if dots > 1 else base_parts
        if not base_parts and dots > 1:
            return None
        target = ".".join(base_parts)
        if imp.module:
            target = f"{target}.{imp.module}" if target else imp.module
        return self._resolve_absolute(target)

    # ------------------------------------------------------------------ #
    def dependencies(self, imports: List[Import]) -> Dict[str, List[str]]:
        """Build module -> sorted list of local dependency modules."""
        deps: Dict[str, Set[str]] = {}
        for imp in imports:
            target = self.resolve_import(imp)
            if target is None:
                continue
            src = module_name_for(imp.file)
            if target == src:
                continue
            # Depend on the package root, not deep submodule, for stability.
            deps.setdefault(src, set()).add(target)
        return {k: sorted(v) for k, v in sorted(deps.items())}
