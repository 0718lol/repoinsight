"""Declarative architecture layer rules.

Rules format (plain dict, easy to load from JSON):

    {
      "forbidden_edges": [
        ["ui.*", "core.internal.*"]   # importer pattern, imported pattern
      ]
    }

Patterns are fnmatch globs matched against dotted module names.
"""

from __future__ import annotations

import fnmatch
from typing import Dict, List

from .cycles import Finding


def check_layers(module_dependencies: Dict[str, List[str]], rules: Dict) -> List[Finding]:
    patterns: List[List[str]] = rules.get("forbidden_edges", []) or []
    findings: List[Finding] = []
    for importer in sorted(module_dependencies):
        for imported in module_dependencies[importer]:
            for pat_importer, pat_imported in patterns:
                if fnmatch.fnmatch(importer, pat_importer) and \
                        fnmatch.fnmatch(imported, pat_imported):
                    findings.append(
                        Finding(
                            kind="layer_violation",
                            severity="error",
                            message=f"违反分层规则:{importer} → {imported}(规则:{pat_importer} 禁止 → {pat_imported})",
                            items=[importer, imported],
                        )
                    )
    findings.sort(key=lambda f: f.message)
    return findings
