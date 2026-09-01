"""Dead code detection.

Heuristic and conservative: a function is reported only when there is no
evidence anywhere in the project that it is used. Evidence = it appears as
a resolved call edge target, or its simple name appears in any raw call
expression, class base, or decorator. Entry-point style names are excluded
because they are usually invoked from outside the codebase.
"""

from __future__ import annotations

import fnmatch
from typing import List, Set

from ..models import AnalysisResult
from .cycles import Finding

# Names commonly invoked from outside the code (frameworks, CLIs, tests).
_ENTRYPOINT_NAMES = {"main", "setUp", "tearDown", "setUpClass", "tearDownClass"}
_ENTRYPOINT_PREFIXES = ("test_",)


def _used_simple_names(result: AnalysisResult) -> Set[str]:
    """All names that appear as call targets, bases or decorators.

    For attribute calls like `cart.add(...)` we also record the attribute
    name itself, so instance-method usage keeps methods alive.
    """
    used: Set[str] = set()
    for sym in result.symbols:
        for call in sym.calls:
            used.add(call)
            used.add(call.split(".")[0])
            used.add(call.rsplit(".", 1)[-1])
        used.update(sym.bases)
        used.update(sym.decorators)
    return used


def find_dead_symbols(result: AnalysisResult, extra_entrypoints: List[str] = None) -> List[Finding]:
    called: Set[str] = {callee for _, callee in result.call_edges}
    used_names = _used_simple_names(result)
    findings: List[Finding] = []
    for sym in result.symbols:
        if not sym.is_function_like:
            continue
        name = sym.name
        if name.startswith("__") and name.endswith("__"):
            continue
        if _is_entrypoint(name, extra_entrypoints):
            continue
        if sym.qualified_name in called:
            continue
        if name in used_names:
            continue  # called somewhere but we could not resolve it; be safe
        findings.append(
            Finding(
                kind="dead_symbol",
                severity="warning",
                message=f"项目内从未被调用:{sym.qualified_name}",
                items=[sym.file, str(sym.line_start)],
            )
        )
    findings.sort(key=lambda f: f.message)
    return findings


def _is_entrypoint(name: str, extra: List[str] = None) -> bool:
    """Entry-point style names are usually invoked from outside the code."""
    if name in _ENTRYPOINT_NAMES or name.startswith(_ENTRYPOINT_PREFIXES):
        return True
    for pattern in extra or []:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def find_unused_imports(result: AnalysisResult) -> List[Finding]:
    """Report internal imports whose names never appear in the importer file.

    Limitation (documented): we only see calls/bases/decorators, so a name
    used in a bare expression or type alias may be a false positive.
    """
    # file -> names referenced in code
    used_by_file: dict = {}
    for sym in result.symbols:
        names = used_by_file.setdefault(sym.file, set())
        for call in sym.calls:
            names.add(call)
            names.add(call.split(".")[0])
        names.update(sym.bases)
        names.update(sym.decorators)

    findings: List[Finding] = []
    for imp in result.imports:
        if "*" in imp.names:
            continue
        used = used_by_file.get(imp.file, set())
        unused = [n for n in imp.names if n not in used and f"{imp.module}.{n}" not in used]
        if unused:
            findings.append(
                Finding(
                    kind="unused_import",
                    severity="warning",
                    message=f"导入了但从未使用:{', '.join(unused)}",
                    items=[imp.file, f"{imp.module}: {', '.join(unused)}", str(imp.line)],
                )
            )
    findings.sort(key=lambda f: (f.items[0], f.message))
    return findings
