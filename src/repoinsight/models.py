"""Shared data models used across the analysis pipeline."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class SourceFile:
    """A single source file discovered during scanning."""

    path: str              # path relative to repo root, posix style
    absolute_path: str
    language: str          # e.g. "python", "javascript", "unknown"
    lines_total: int = 0
    lines_code: int = 0
    lines_comment: int = 0
    lines_blank: int = 0

    def to_dict(self) -> Dict:
        return dataclasses.asdict(self)


@dataclass
class Symbol:
    """A top-level or nested definition found in a file.

    kind is one of: "module", "class", "function", "method", "async_function".
    qualified_name includes enclosing scopes, e.g. "pkg.mod.Class.method".
    """

    kind: str
    name: str
    qualified_name: str
    file: str
    line_start: int
    line_end: int
    parent: Optional[str] = None            # qualified name of enclosing symbol
    calls: List[str] = field(default_factory=list)   # raw call names inside body
    decorators: List[str] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)   # for classes
    complexity: int = 1                     # cyclomatic complexity

    @property
    def is_function_like(self) -> bool:
        return self.kind in ("function", "method", "async_function")

    def to_dict(self) -> Dict:
        return dataclasses.asdict(self)


@dataclass
class Import:
    """An import statement resolved as far as possible statically."""

    file: str
    module: str              # imported module path, e.g. "pkg.sub.mod"
    names: List[str]         # imported names ("*" for star imports)
    line: int
    is_relative: bool = False
    level: int = 0            # number of dots for relative imports (0 = absolute)
    resolved_local: Optional[str] = None     # file path or package dir, if internal

    def to_dict(self) -> Dict:
        return dataclasses.asdict(self)


@dataclass
class AnalysisResult:
    """Aggregated result of analyzing a repository."""

    root: str
    files: List[SourceFile] = field(default_factory=list)
    symbols: List[Symbol] = field(default_factory=list)
    imports: List[Import] = field(default_factory=list)
    # module (dotted path) -> list of dotted module paths it depends on
    module_dependencies: Dict[str, List[str]] = field(default_factory=dict)
    # qualified caller -> sorted set of qualified/raw callees actually resolved
    call_edges: List[Tuple[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "root": self.root,
            "files": [f.to_dict() for f in self.files],
            "symbols": [s.to_dict() for s in self.symbols],
            "imports": [i.to_dict() for i in self.imports],
            "module_dependencies": self.module_dependencies,
            "call_edges": [list(e) for e in self.call_edges],
            "errors": self.errors,
        }
