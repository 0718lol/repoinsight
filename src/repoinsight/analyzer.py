"""RepoAnalyzer: orchestrates scanning, parsing, graph building and metrics."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .call_graph import CallGraph
from .models import AnalysisResult, Symbol
from .module_graph import ModuleGraph
from .parsers import parser_for
from .scanner import RepoScanner


class RepoAnalyzer:
    """Analyze a repository end-to-end."""

    def __init__(self, root: str, **scanner_kwargs):
        self.root = str(Path(root).resolve())
        self.scanner = RepoScanner(self.root, **scanner_kwargs)
        self.result = AnalysisResult(root=self.root)

    # ------------------------------------------------------------------ #
    def analyze(self) -> AnalysisResult:
        files = self.scanner.scan()
        self.result.files = files

        symbols: List[Symbol] = []
        imports = []
        for f in files:
            parser = parser_for(f.language, f.path)
            if parser is None:
                continue
            try:
                parser.parse(Path(f.absolute_path).read_text(encoding="utf-8", errors="replace"))
            except (ValueError, OSError) as exc:
                self.result.errors.append(f"{f.path}: {exc}")
                continue
            symbols.extend(parser.symbols)
            imports.extend(parser.imports)

        self.result.symbols = symbols
        self.result.imports = imports

        # Qualify file-relative symbol names with their module path so that
        # qualified_name is unique repo-wide: pkg/mod.py "Engine.start"
        # becomes "pkg.core.Engine.start" when mod.py declares package core.
        from .module_graph import _file_to_module  # local import: single source of truth
        for sym in symbols:
            module = _file_to_module(sym.file)
            if module and module != "__root__":
                sym.qualified_name = f"{module}.{sym.qualified_name}"
                sym.parent = f"{module}.{sym.parent}" if sym.parent else None

        mg = ModuleGraph(files)
        self.result.module_dependencies = mg.dependencies(imports)

        cg = CallGraph(symbols, imports)
        cg.build()
        self.result.call_edges = cg.to_edge_list()

        self._call_graph = cg
        self._module_graph = mg
        return self.result

    # ------------------------------------------------------------------ #
    def callers_of(self, qualified_name: str) -> List[str]:
        return self._call_graph.callers_of(qualified_name)

    def callees_of(self, qualified_name: str) -> List[str]:
        return self._call_graph.callees_of(qualified_name)

    # ------------------------------------------------------------------ #
    def file_metrics(self) -> List[Dict]:
        """Per-file LOC stats sorted by code lines, descending."""
        rows = [
            {
                "path": f.path,
                "language": f.language,
                "code": f.lines_code,
                "comment": f.lines_comment,
                "blank": f.lines_blank,
                "total": f.lines_total,
            }
            for f in self.result.files
        ]
        rows.sort(key=lambda r: r["code"], reverse=True)
        return rows

    def complexity_report(self, top: int = 25) -> List[Dict]:
        """Most complex functions/methods first."""
        rows = [
            {
                "name": s.qualified_name,
                "file": s.file,
                "line": s.line_start,
                "complexity": s.complexity,
                "kind": s.kind,
            }
            for s in self.result.symbols if s.is_function_like
        ]
        rows.sort(key=lambda r: r["complexity"], reverse=True)
        return rows[:top]

    def coupling_report(self) -> Dict[str, Dict[str, int]]:
        """Fan-out (imports) and fan-in (imported by) per module."""
        fan_out: Dict[str, int] = {
            mod: len(deps) for mod, deps in self.result.module_dependencies.items()
        }
        fan_in: Dict[str, int] = {}
        for deps in self.result.module_dependencies.values():
            for dep in deps:
                fan_in[dep] = fan_in.get(dep, 0) + 1
        modules = sorted(set(fan_out) | set(fan_in))
        return {
            mod: {
                "fan_in": fan_in.get(mod, 0),
                "fan_out": fan_out.get(mod, 0),
            }
            for mod in modules
        }

    def summary(self) -> Dict:
        py_symbols = [s for s in self.result.symbols]
        return {
            "root": self.root,
            "files": len(self.result.files),
            "python_files": sum(1 for f in self.result.files if f.language == "python"),
            "total_lines": sum(f.lines_total for f in self.result.files),
            "code_lines": sum(f.lines_code for f in self.result.files),
            "symbols": len(py_symbols),
            "classes": sum(1 for s in py_symbols if s.kind == "class"),
            "functions": sum(1 for s in py_symbols if s.is_function_like),
            "internal_imports": len(self.result.imports),
            "module_dependencies": len(self.result.module_dependencies),
            "call_edges": len(self.result.call_edges),
            "parse_errors": len(self.result.errors),
        }
