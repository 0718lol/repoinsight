"""Output writers: JSON, DOT graphs, plain-text summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .analyzer import RepoAnalyzer


# ---------------------------------------------------------------------- #
def write_json(analyzer: RepoAnalyzer, path: str) -> str:
    result = analyzer.result
    payload = {
        "summary": analyzer.summary(),
        "analysis": result.to_dict(),
    }
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(out)


# ---------------------------------------------------------------------- #
def _dot_escape(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')


def write_module_dot(analyzer: RepoAnalyzer, path: str) -> str:
    """Module dependency graph as a Graphviz DOT file."""
    deps = analyzer.result.module_dependencies
    lines = [
        "digraph module_dependencies {",
        '  rankdir="LR";',
        '  node [shape=box, style="rounded,filled", fillcolor="#eef3fb", fontname="Helvetica"];',
    ]
    modules = set(deps)
    for targets in deps.values():
        modules.update(targets)
    for mod in sorted(modules):
        lines.append(f'  "{_dot_escape(mod)}";')
    for src, targets in sorted(deps.items()):
        for dst in targets:
            lines.append(f'  "{_dot_escape(src)}" -> "{_dot_escape(dst)}";')
    lines.append("}")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out)


def write_call_dot(analyzer: RepoAnalyzer, path: str, max_nodes: int = 120) -> str:
    """Call graph as DOT, limited to the busiest functions for readability."""
    edges = analyzer.result.call_edges
    degree: Dict[str, int] = {}
    for src, dst in edges:
        degree[src] = degree.get(src, 0) + 1
        degree[dst] = degree.get(dst, 0) + 1
    keep = {n for n, _ in sorted(degree.items(), key=lambda kv: -kv[1])[:max_nodes]}
    lines = [
        "digraph call_graph {",
        '  rankdir="LR";',
        '  node [shape=ellipse, fontname="Helvetica", fontsize=10];',
    ]
    for node in sorted(keep):
        lines.append(f'  "{_dot_escape(node)}";')
    for src, dst in edges:
        if src in keep and dst in keep:
            lines.append(f'  "{_dot_escape(src)}" -> "{_dot_escape(dst)}";')
    lines.append("}")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out)


# ---------------------------------------------------------------------- #
def _rule(char: str = "-", width: int = 72) -> str:
    return char * width


def write_summary_text(analyzer: RepoAnalyzer, path: Optional[str] = None) -> str:
    """Human-readable summary; prints to stdout if path is None."""
    s = analyzer.summary()
    lines: List[str] = []
    lines.append("REPOINSIGHT SUMMARY")
    lines.append(_rule("="))
    lines.append(f"Root:               {s['root']}")
    lines.append(f"Files:              {s['files']} ({s['python_files']} python)")
    lines.append(f"Lines (code/total): {s['code_lines']} / {s['total_lines']}")
    lines.append(f"Symbols:            {s['symbols']} ({s['classes']} classes, {s['functions']} functions)")
    lines.append(f"Module dep edges:   {s['module_dependencies']}")
    lines.append(f"Call graph edges:   {s['call_edges']}")
    lines.append(f"Parse errors:       {s['parse_errors']}")
    lines.append("")

    lines.append("TOP FILES BY CODE LINES")
    lines.append(_rule())
    for row in analyzer.file_metrics()[:15]:
        lines.append(f"  {row['code']:>7}  {row['path']}")
    lines.append("")

    lines.append("HIGHEST COMPLEXITY")
    lines.append(_rule())
    for row in analyzer.complexity_report(top=15):
        lines.append(f"  {row['complexity']:>4}   {row['name']}  ({row['file']}:{row['line']})")
    lines.append("")

    lines.append("MOST COUPLED MODULES (fan-in + fan-out)")
    lines.append(_rule())
    coupling = analyzer.coupling_report()
    ranked = sorted(
        coupling.items(), key=lambda kv: -(kv[1]["fan_in"] + kv[1]["fan_out"])
    )[:15]
    for mod, c in ranked:
        lines.append(f"  in={c['fan_in']:<3} out={c['fan_out']:<3} {mod}")

    text = "\n".join(lines) + "\n"
    if path is None:
        return text
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return str(out)
