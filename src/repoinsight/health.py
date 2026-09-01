"""Architecture health score: one 0-100 number plus per-dimension penalties.

Explainable by design: every point lost maps to a concrete finding so the
report can show exactly WHY the score is what it is.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List

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


def score(result: AnalysisResult, layer_rules: Dict = None) -> HealthScore:
    findings = run_all(result, rules=layer_rules)
    functions = [s for s in result.symbols if s.is_function_like]
    dims: List[Dimension] = []

    # 1. circular dependencies: hard errors, weight heaviest
    cycles = [f for f in findings if f.kind == "circular_dependency"]
    cyc_penalty = min(36, 12 * len(cycles))
    dims.append(Dimension(
        name="循环依赖",
        penalty=cyc_penalty,
        max_penalty=36,
        detail="、".join(" ↔ ".join(f.items) for f in cycles[:3]) or "未发现",
    ))

    # 2. dead code ratio
    dead = [f for f in findings if f.kind == "dead_symbol"]
    ratio = (len(dead) / len(functions)) if functions else 0.0
    dead_penalty = min(20, round(ratio * 60))
    dims.append(Dimension(
        name="死代码比例",
        penalty=dead_penalty,
        max_penalty=20,
        detail=f"{len(dead)}/{len(functions)} 个函数无人调用" if functions else "无函数",
    ))

    # 3. complexity: share of functions with cx >= 10
    hot = [s for s in functions if s.complexity >= 10]
    hot_ratio = (len(hot) / len(functions)) if functions else 0.0
    cx_penalty = min(24, round(hot_ratio * 80))
    worst = max(functions, key=lambda s: s.complexity, default=None)
    detail = f"{len(hot)} 个函数复杂度 ≥10" + (
        f",最复杂 {worst.qualified_name}(cx {worst.complexity})" if worst else ""
    )
    dims.append(Dimension(name="复杂度", penalty=cx_penalty, max_penalty=24, detail=detail))

    # 4. coupling: heavily depended-on or depending modules
    fan: Dict[str, int] = {}
    for mod, deps in result.module_dependencies.items():
        fan[mod] = fan.get(mod, 0) + len(deps)
        for dep in deps:
            fan[dep] = fan.get(dep, 0) + 1
    heavy = sorted((m for m, v in fan.items() if v >= 12), key=lambda m: -fan[m])
    coup_penalty = min(12, 4 * len(heavy))
    dims.append(Dimension(
        name="模块耦合",
        penalty=coup_penalty,
        max_penalty=12,
        detail="、".join(heavy[:3]) + (f" 等 {len(heavy)} 个" if len(heavy) > 3 else "")
        if heavy else "均在合理范围",
    ))

    # 5. unused imports: small signal but free to include
    unused = [f for f in findings if f.kind == "unused_import"]
    imp_penalty = min(8, 2 * len(unused))
    dims.append(Dimension(
        name="无效导入",
        penalty=imp_penalty,
        max_penalty=8,
        detail=f"{len(unused)} 处" if unused else "未发现",
    ))

    total = max(0, 100 - sum(d.penalty for d in dims))
    for floor, label, css in _GRADES:
        if total >= floor:
            return HealthScore(total=total, grade=label, grade_class=css, dimensions=dims)
    return HealthScore(total=total, grade=_GRADES[-1][1], grade_class=_GRADES[-1][2],
                       dimensions=dims)
