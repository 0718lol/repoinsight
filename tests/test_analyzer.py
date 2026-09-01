"""End-to-end analyzer tests plus metrics reports."""

from conftest import SRC  # noqa: F401


def test_summary_counts(analysis):
    s = analysis.summary()
    assert s["python_files"] == 7
    assert s["files"] == 9
    assert s["parse_errors"] == 0
    assert s["classes"] >= 1
    assert s["functions"] >= 10


def test_symbols_found(analysis):
    names = {s.qualified_name for s in analysis.result.symbols}
    assert "pkg.core.Engine" in names
    assert "pkg.core.Engine.start" in names
    assert "app.main" in names


def test_internal_dependencies(analysis):
    deps = analysis.result.module_dependencies
    assert "pkg.cyclic_a" in deps["pkg.cyclic_b"]
    assert "pkg.cyclic_b" in deps["pkg.cyclic_a"]
    assert "pkg.core" in deps["pkg.helpers"]
    assert "os" not in deps  # external imports never appear


def test_call_edges_resolved(analysis):
    edges = set(analysis.result.call_edges)
    assert ("app.main", "pkg.deep.level1") in edges
    assert ("pkg.core.Engine.start", "pkg.helpers.helper_used") in edges


def test_who_calls(analysis):
    assert "pkg.core.Engine.start" in analysis.callers_of("pkg.helpers.helper_used")
    assert "pkg.deep.level1" in analysis.callees_of("app.main")


def test_complexity_report_sorted(analysis):
    rows = analysis.complexity_report(top=5)
    assert len(rows) <= 5
    cxs = [r["complexity"] for r in rows]
    assert cxs == sorted(cxs, reverse=True)
    top = rows[0]
    assert top["name"] == "pkg.core.Engine.complex_logic"
    # for + if + elif + while = 4 branches -> cx 5
    assert top["complexity"] == 5


def test_coupling_report(analysis):
    coupling = analysis.coupling_report()
    entry = coupling["pkg.models_never_imported"] if "pkg.models_never_imported" in coupling else coupling.get("pkg.core")
    assert entry is not None
    assert entry["fan_in"] >= 1  # helpers + app import pkg.core transitively


def test_file_metrics_sorted(analysis):
    rows = analysis.file_metrics()
    codes = [r["code"] for r in rows]
    assert codes == sorted(codes, reverse=True)
    assert rows[0]["path"] == "pkg/core.py"


def test_to_dict_roundtrip(analysis):
    payload = analysis.result.to_dict()
    assert payload["root"] == analysis.root
    assert len(payload["symbols"]) == len(analysis.result.symbols)
    assert all(isinstance(e, list) and len(e) == 2 for e in payload["call_edges"])
