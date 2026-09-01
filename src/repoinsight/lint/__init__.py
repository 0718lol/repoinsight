"""Lint subpackage: cycles, dead code, layer rules."""

from .cycles import Finding, find_cycles
from .deadcode import find_dead_symbols, find_unused_imports
from .layers import check_layers

__all__ = [
    "Finding",
    "find_cycles",
    "find_dead_symbols",
    "find_unused_imports",
    "check_layers",
]


def run_all(result, rules=None):
    """Run every check against an AnalysisResult; rules optional (layers)."""
    findings: list = []
    for cycle in find_cycles(result.module_dependencies):
        findings.append(
            Finding(
                kind="circular_dependency",
                severity="error",
                message="circular import: " + " -> ".join(cycle + [cycle[0]]),
                items=cycle,
            )
        )
    findings.extend(find_dead_symbols(result))
    findings.extend(find_unused_imports(result))
    if rules:
        findings.extend(check_layers(result.module_dependencies, rules))
    return findings
