"""Data preparation for the self-contained interactive report.

This module deliberately knows nothing about HTML, CSS, or browser behavior.
It turns an analyzed repository into a bounded, JSON-serializable payload for
the report renderer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set

from ..analyzer import RepoAnalyzer
from ..health import score as health_score

MAX_SOURCE_LINES = 500
MAX_CALL_NODES = 80
MAX_GRAPH_MODULES = 150
MAX_EMBEDDED_FILES = 200


def aggregate_deps_by_package(deps: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Collapse a module-level dependency graph to top-level packages."""
    out: Dict[str, Set[str]] = {}
    for src, targets in deps.items():
        pkg = src.split(".")[0]
        for target in targets:
            target_pkg = target.split(".")[0]
            if target_pkg == pkg:
                continue
            out.setdefault(pkg, set()).add(target_pkg)
    return {key: sorted(value) for key, value in sorted(out.items())}


def collect_data(analyzer: RepoAnalyzer) -> Dict:
    """Build the bounded data contract consumed by the report frontend."""
    result = analyzer.result

    degree: Dict[str, int] = {}
    for source, target in result.call_edges:
        degree[source] = degree.get(source, 0) + 1
        degree[target] = degree.get(target, 0) + 1
    keep = {
        name for name, _ in sorted(degree.items(), key=lambda item: -item[1])[:MAX_CALL_NODES]
    }

    sources: Dict[str, List[str]] = {}
    truncated: Dict[str, int] = {}
    python_files = sorted(
        (source_file for source_file in result.files if source_file.language == "python"),
        key=lambda source_file: -source_file.lines_code,
    )
    for source_file in python_files[:MAX_EMBEDDED_FILES]:
        try:
            full_source = Path(source_file.absolute_path).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue
        lines = full_source.splitlines()
        if len(lines) > MAX_SOURCE_LINES:
            truncated[source_file.path] = len(lines)
        sources[source_file.path] = lines[:MAX_SOURCE_LINES]

    modules = sorted(
        set(result.module_dependencies)
        | {dependency for dependencies in result.module_dependencies.values() for dependency in dependencies}
    )
    graph_mode = "module"
    module_deps = result.module_dependencies
    if len(modules) > MAX_GRAPH_MODULES:
        graph_mode = "package"
        module_deps = aggregate_deps_by_package(result.module_dependencies)
        modules = sorted(
            set(module_deps)
            | {dependency for dependencies in module_deps.values() for dependency in dependencies}
        )

    return {
        "summary": analyzer.summary(),
        "health": health_score(result).to_dict(),
        "graphMode": graph_mode,
        "modules": modules,
        "moduleDeps": module_deps,
        "callEdges": [
            list(edge) for edge in result.call_edges if edge[0] in keep and edge[1] in keep
        ],
        "files": analyzer.file_metrics(),
        "complexity": analyzer.complexity_report(top=40),
        "coupling": analyzer.coupling_report(),
        "symbols": [
            {
                "kind": symbol.kind,
                "name": symbol.name,
                "q": symbol.qualified_name,
                "file": symbol.file,
                "line": symbol.line_start,
                "end": symbol.line_end,
                "cx": symbol.complexity,
            }
            for symbol in result.symbols
        ],
        "sources": sources,
        "truncatedFiles": truncated,
        "embeddedLimit": MAX_EMBEDDED_FILES,
    }
