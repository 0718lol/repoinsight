"""Tests for the lint package: cycles, dead code, layers."""

from conftest import SRC  # noqa: F401  (sys.path setup)

from repoinsight.lint import (
    Finding,
    check_layers,
    find_cycles,
    find_dead_symbols,
    find_unused_imports,
    run_all,
)
from repoinsight.models import AnalysisResult, Import, Symbol


def _result(deps=None, symbols=None, imports=None, call_edges=None) -> AnalysisResult:
    r = AnalysisResult(root="/x")
    r.module_dependencies = deps or {}
    r.symbols = symbols or []
    r.imports = imports or []
    r.call_edges = call_edges or []
    return r


def _sym(kind, name, qualified, file, calls=None, line=1):
    return Symbol(kind=kind, name=name, qualified_name=qualified, file=file,
                  line_start=line, line_end=line + 3, calls=calls or [])


# ------------------------------------------------------------------ cycles
def test_simple_two_node_cycle():
    deps = {"a": ["b"], "b": ["a"]}
    cycles = find_cycles(deps)
    assert cycles == [["a", "b"]]


def test_self_loop_is_cycle():
    assert find_cycles({"a": ["a"]}) == [["a"]]


def test_no_cycle():
    deps = {"a": ["b"], "b": ["c"], "c": []}
    assert find_cycles(deps) == []


def test_three_node_cycle_and_acyclic_mixed():
    deps = {"a": ["b"], "b": ["c"], "c": ["a"], "d": ["a"]}
    assert find_cycles(deps) == [["a", "b", "c"]]


def test_cycle_members_deduped_from_graph_nodes():
    # b is only referenced as a dependency of a; the reverse edge completes it
    deps = {"a": ["b"], "b": ["a"]}
    assert find_cycles(deps) == [["a", "b"]]


# ---------------------------------------------------------------- deadcode
def test_dead_symbol_detected():
    syms = [
        _sym("function", "used", "m.used", "m.py"),
        _sym("function", "lonely", "m.lonely", "m.py"),
    ]
    result = _result(symbols=syms, call_edges=[("m.other", "m.used")])
    dead = [f.message for f in find_dead_symbols(result)]
    assert any("m.lonely" in msg for msg in dead)
    assert not any("m.used" in msg for msg in dead)


def test_entrypoints_not_dead():
    syms = [_sym("function", "main", "m.main", "m.py"),
            _sym("function", "test_it", "m.test_it", "m.py"),
            _sym("method", "__init__", "m.C.__init__", "m.py")]
    result = _result(symbols=syms)
    assert find_dead_symbols(result) == []


def test_unresolved_call_name_keeps_symbol_alive():
    # f() calls helper() but the edge cannot be resolved; any sibling with
    # the same simple name must NOT be flagged dead (conservative rule).
    # caller itself has no callers, so it is legitimately reported.
    syms = [
        _sym("function", "caller", "m.caller", "m.py", calls=["helper"]),
        _sym("function", "helper", "other.helper", "other.py"),
    ]
    result = _result(symbols=syms)
    dead_msgs = [f.message for f in find_dead_symbols(result)]
    assert not any("other.helper" in m for m in dead_msgs)
    assert any("m.caller" in m for m in dead_msgs)


def test_unused_import_detected():
    imports = [Import(file="m.py", module="json", names=["dumps"], line=1)]
    syms = [_sym("function", "f", "m.f", "m.py", calls=["os_path"])]
    result = _result(symbols=syms, imports=imports)
    msgs = [f.message for f in find_unused_imports(result)]
    assert any("dumps" in m for m in msgs)


def test_used_import_not_flagged():
    imports = [Import(file="m.py", module="json", names=["dumps"], line=1)]
    syms = [_sym("function", "f", "m.f", "m.py", calls=["dumps"])]
    result = _result(symbols=syms, imports=imports)
    assert find_unused_imports(result) == []


def test_star_import_never_flagged():
    imports = [Import(file="m.py", module="xmod", names=["*"], line=1)]
    result = _result(imports=imports)
    assert find_unused_imports(result) == []


# ------------------------------------------------------------------ layers
def test_layer_violation_matches_glob():
    deps = {"ui.app": ["core.engine"], "core.engine": ["util.x"]}
    rules = {"forbidden_edges": [["ui.*", "core.*"]]}
    findings = check_layers(deps, rules)
    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].kind == "layer_violation"


def test_layer_rule_allows_others():
    deps = {"ui.app": ["ui.helpers"]}
    rules = {"forbidden_edges": [["ui.*", "core.*"]]}
    assert check_layers(deps, rules) == []


# ----------------------------------------------------------------- run_all
def test_run_all_aggregates_and_orders():
    syms = [_sym("function", "ghost", "m.ghost", "m.py")]
    imports = [Import(file="m.py", module="json", names=["dumps"], line=1)]
    result = _result(deps={"a": ["b"], "b": ["a"]}, symbols=syms, imports=imports)
    findings = run_all(result)
    kinds = {f.kind for f in findings}
    assert kinds == {"circular_dependency", "dead_symbol", "unused_import"}


def test_run_all_with_rules():
    result = _result(deps={"ui.app": ["core.x"]})
    findings = run_all(result, rules={"forbidden_edges": [["ui.*", "core.*"]]})
    assert any(f.kind == "layer_violation" for f in findings)


def test_finding_to_dict():
    f = Finding("dead_symbol", "warning", "msg", ["a.py"])
    assert f.to_dict() == {"kind": "dead_symbol", "severity": "warning",
                           "message": "msg", "items": ["a.py"]}
