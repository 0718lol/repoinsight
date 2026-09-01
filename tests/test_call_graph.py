"""Tests for call graph resolution."""

from conftest import SRC  # noqa: F401

from repoinsight.call_graph import CallGraph
from repoinsight.models import Import, Symbol


def _sym(kind, name, qualified, file, calls=None, parent=None):
    return Symbol(kind=kind, name=name, qualified_name=qualified, file=file,
                  line_start=1, line_end=2, calls=calls or [], parent=parent)


def test_resolution_via_import():
    symbols = [
        _sym("function", "helper", "pkg.helpers.helper", "pkg/helpers.py"),
        _sym("function", "user", "pkg.core.user", "pkg/core.py", calls=["helper"]),
    ]
    imports = [Import(file="pkg/core.py", module="pkg.helpers", names=["helper"], line=1)]
    graph = CallGraph(symbols, imports)
    graph.build()
    assert graph.callees_of("pkg.core.user") == ["pkg.helpers.helper"]
    assert graph.callers_of("pkg.helpers.helper") == ["pkg.core.user"]


def test_resolution_same_module_sibling():
    symbols = [
        _sym("function", "leaf", "pkg.mod.leaf", "pkg/mod.py"),
        _sym("function", "caller", "pkg.mod.caller", "pkg/mod.py", calls=["leaf"]),
    ]
    graph = CallGraph(symbols, [])
    graph.build()
    assert graph.callees_of("pkg.mod.caller") == ["pkg.mod.leaf"]


def test_resolution_self_method():
    symbols = [
        _sym("class", "C", "pkg.m.C", "pkg/m.py"),
        _sym("method", "a", "pkg.m.C.a", "pkg/m.py", calls=["self.b"], parent="pkg.m.C"),
        _sym("method", "b", "pkg.m.C.b", "pkg/m.py", parent="pkg.m.C"),
    ]
    graph = CallGraph(symbols, [])
    graph.build()
    assert graph.callees_of("pkg.m.C.a") == ["pkg.m.C.b"]


def test_unresolved_calls_are_dropped():
    symbols = [_sym("function", "f", "m.f", "m.py", calls=["unknown_thing"])]
    graph = CallGraph(symbols, [])
    graph.build()
    assert graph.to_edge_list() == []


def test_self_edge_excluded():
    symbols = [_sym("function", "rec", "m.rec", "m.py", calls=["rec"])]
    graph = CallGraph(symbols, [])
    graph.build()
    assert graph.to_edge_list() == []


def test_same_name_prefers_same_parent():
    symbols = [
        _sym("class", "A", "m.A", "m.py"),
        _sym("method", "run", "m.A.run", "m.py", parent="m.A"),
        _sym("class", "B", "m.B", "m.py"),
        _sym("method", "run", "m.B.run", "m.py", calls=["self.run"], parent="m.B"),
    ]
    graph = CallGraph(symbols, [])
    graph.build()
    # "self.run" inside B resolves to B.run itself -> self-edge is dropped
    assert graph.callees_of("m.B.run") == []


# ---------------- typed variables and inheritance ----------------
def _symx(kind, name, qualified, file, calls=None, parent=None, var_types=None, bases=None):
    return Symbol(kind=kind, name=name, qualified_name=qualified, file=file,
                  line_start=1, line_end=2, calls=calls or [], parent=parent,
                  var_types=var_types or {}, bases=bases or [])


def test_typed_variable_call_resolves():
    symbols = [
        _symx("class", "Cart", "shop.Cart", "shop/cart.py"),
        _symx("method", "add", "shop.Cart.add", "shop/cart.py", parent="shop.Cart"),
        _symx("function", "user", "app.user", "app.py",
              calls=["c.add"], var_types={"c": "Cart"}),
    ]
    imports = [Import(file="app.py", module="shop", names=["Cart"], line=1)]
    graph = CallGraph(symbols, imports)
    graph.build()
    assert graph.callees_of("app.user") == ["shop.Cart.add"]


def test_typed_variable_same_module_class():
    symbols = [
        _symx("class", "Cart", "m.Cart", "m.py"),
        _symx("method", "add", "m.Cart.add", "m.py", parent="m.Cart"),
        _symx("function", "user", "m.user", "m.py",
              calls=["c.add"], var_types={"c": "Cart"}),
    ]
    graph = CallGraph(symbols, [])
    graph.build()
    assert graph.callees_of("m.user") == ["m.Cart.add"]


def test_inherited_method_via_self():
    symbols = [
        _symx("class", "Base", "m.Base", "m.py"),
        _symx("method", "greet", "m.Base.greet", "m.py", parent="m.Base"),
        _symx("class", "Child", "m.Child", "m.py", bases=["Base"]),
        _symx("method", "run", "m.Child.run", "m.py",
              calls=["self.greet"], parent="m.Child"),
    ]
    graph = CallGraph(symbols, [])
    graph.build()
    assert graph.callees_of("m.Child.run") == ["m.Base.greet"]


def test_typed_variable_inherited_method():
    symbols = [
        _symx("class", "Base", "m.Base", "m.py"),
        _symx("method", "greet", "m.Base.greet", "m.py", parent="m.Base"),
        _symx("class", "Child", "m.Child", "m.py", bases=["Base"]),
        _symx("function", "user", "m.user", "m.py",
              calls=["c.greet"], var_types={"c": "Child"}),
    ]
    graph = CallGraph(symbols, [])
    graph.build()
    assert graph.callees_of("m.user") == ["m.Base.greet"]


def test_typed_unknown_class_stays_unresolved():
    symbols = [
        _symx("function", "user", "m.user", "m.py",
              calls=["x.add"], var_types={"x": "Missing"}),
    ]
    graph = CallGraph(symbols, [])
    graph.build()
    assert graph.to_edge_list() == []
