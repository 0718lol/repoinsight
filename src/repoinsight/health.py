"""Architecture health score: one 0-100 number plus per-dimension penalties.

Explainable by design: every point lost maps to a concrete finding so the
report can show exactly WHY the score is what it is.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .lint import run_all
from .models import AnalysisResult

# grade -> (min score, label, css color class)
_GRADES = (
    (85, "优秀", "good"),
    (70, "良好", "ok"),
    (55, "及格", "warn"),
    (0, "需要重构", "bad"),
)


@dataclass
class Dimension:
    """One scoring dimension and why it lost points."""

    name: str                     # Chinese label
    penalty: int                  # points lost (>= 0)
    max_penalty: int
    detail: str                   # human-readable Chinese reason

    def to_dict(self) -> Dict:
        return dataclasses.asdict(self)


@dataclass
class HealthScore:
    total: int
    grade: str                    # Chinese label
    grade_class: str              # css class for report colors
    dimensions: List[Dimension] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "total": self.total,
            "grade": self.grade,
            "grade_class": self.grade_class,
            "dimensions": [d.to_dict() for d in self.dimensions],
        }


def _cycle_dimension(findings: list) -> Dimension:
    cycles = [f for f in findings if f.kind == "circular_dependency"]
    return Dimension(
        name="循环依赖",
        penalty=min(36, 12 * len(cycles)),
        max_penalty=36,
        detail="、".join(" ↔ ".join(f.items) for f in cycles[:3]) or "未发现",
    )

def _dead_code_dimension(findings: list, functions: list) -> Dimension:
    dead = [f for f in findings if f.kind == "dead_symbol"]
    ratio = (len(dead) / len(functions)) if functions else 0.0
    return Dimension(
        name="死代码比例",
        penalty=min(20, round(ratio * 60)),
        max_penalty=20,
        detail=f"{len(dead)}/{len(functions)} 个函数无人调用" if functions else "无函数",
    )

def _complexity_dimension(functions: list) -> Dimension:
    hot = [s for s in functions if s.complexity >= 10]
    hot_ratio = (len(hot) / len(functions)) if functions else 0.0
    worst = max(functions, key=lambda s: s.complexity, default=None)
    detail = f"{len(hot)} 个函数复杂度 ≥10" + (
        f",最复杂 {worst.qualified_name}(cx {worst.complexity})" if worst else ""
    )
    return Dimension(name="复杂度", penalty=min(24, round(hot_ratio * 80)),
                     max_penalty=24, detail=detail)

def _coupling_dimension(result: AnalysisResult) -> Dimension:
    fan: Dict[str, int] = {}
    for mod, deps in result.module_dependencies.items():
        fan[mod] = fan.get(mod, 0) + len(deps)
        for dep in deps:
            fan[dep] = fan.get(dep, 0) + 1
    heavy = sorted((m for m, v in fan.items() if v >= 12), key=lambda m: -fan[m])
    return Dimension(
        name="模块耦合",
        penalty=min(12, 4 * len(heavy)),
        max_penalty=12,
        detail="、".join(heavy[:3]) + (f" 等 {len(heavy)} 个" if len(heavy) > 3 else "")
        if heavy else "均在合理范围",
    )

def _unused_import_dimension(findings: list) -> Dimension:
    unused = [f for f in findings if f.kind == "unused_import"]
    return Dimension(
        name="无效导入",
        penalty=min(8, 2 * len(unused)),
        max_penalty=8,
        detail=f"{len(unused)} 处" if unused else "未发现",
    )


def _dimensions(result: AnalysisResult, findings: list) -> List[Dimension]:
    functions = [s for s in result.symbols if s.is_function_like]
    return [
        _cycle_dimension(findings),
        _dead_code_dimension(findings, functions),
        _complexity_dimension(functions),
        _coupling_dimension(result),
        _unused_import_dimension(findings),
    ]


def _grade(total: int) -> tuple:
    for floor, label, css in _GRADES:
        if total >= floor:
            return label, css
    return _GRADES[-1][1], _GRADES[-1][2]


def score(result: AnalysisResult, layer_rules: Optional[Dict] = None) -> HealthScore:
    """Calculate the score from independently testable dimensions."""
    findings = run_all(result, rules=layer_rules)
    dims = _dimensions(result, findings)

    total = max(0, 100 - sum(d.penalty for d in dims))
    label, css = _grade(total)
    return HealthScore(total=total, grade=label, grade_class=css, dimensions=dims)
