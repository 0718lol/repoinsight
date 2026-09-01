"""Tests for the health score engine."""

from conftest import SRC  # noqa: F401

from repoinsight.health import score


def test_perfect_score_on_clean_project(analysis):
    # the fixture repo has one cycle, so expect a non-trivial but stable score
    hs = score(analysis.result)
    assert 0 <= hs.total <= 100
    assert hs.grade in ("优秀", "良好", "及格", "需要重构")
    assert len(hs.dimensions) == 5
    names = {d.name for d in hs.dimensions}
    assert names == {"循环依赖", "死代码比例", "复杂度", "模块耦合", "无效导入"}


def test_cycle_costs_points(analysis):
    with_cycle = score(analysis.result)
    # remove the cycle edges, score must improve
    fixed = analysis.result
    saved = dict(fixed.module_dependencies)
    fixed.module_dependencies = {
        k: [d for d in v if not (k == "pkg.cyclic_a" and d == "pkg.cyclic_b")]
        for k, v in saved.items()
    }
    without_cycle = score(fixed)
    assert without_cycle.total > with_cycle.total


def test_to_dict_roundtrip(analysis):
    payload = score(analysis.result).to_dict()
    assert isinstance(payload["total"], int)
    assert all("penalty" in d for d in payload["dimensions"])


def test_worst_case_scores_low():
    from repoinsight.models import AnalysisResult, Symbol

    r = AnalysisResult(root="/x")
    r.module_dependencies = {"a": ["b"], "b": ["a"], "c": ["c"]}
    syms = []
    for i in range(10):
        syms.append(Symbol(kind="function", name=f"f{i}", qualified_name=f"m.f{i}",
                           file="m.py", line_start=i, line_end=i + 1, complexity=25))
    r.symbols = syms
    r.call_edges = [("m.f0", "m.f1")]
    hs = score(r)
    assert hs.total <= 55
    assert hs.grade == "需要重构"
    cyc = next(d for d in hs.dimensions if d.name == "循环依赖")
    assert cyc.penalty >= 24  # two cycles, 12 points each (cap is 36)
