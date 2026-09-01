"""Tests for module naming, import resolution and dependency edges."""

from conftest import SRC  # noqa: F401

from repoinsight.models import Import, SourceFile
from repoinsight.module_graph import ModuleGraph, module_name_for


def test_module_name_for_plain():
    assert module_name_for("pkg/sub/mod.py") == "pkg.sub.mod"


def test_module_name_for_init():
    assert module_name_for("pkg/__init__.py") == "pkg"
    assert module_name_for("__init__.py") == "__root__"


def test_module_name_for_non_python():
    assert module_name_for("docs/readme.md") == "docs/readme"


def _file(path: str, language: str = "python") -> SourceFile:
    return SourceFile(path=path, absolute_path="/" + path, language=language)


def test_absolute_import_resolution():
    files = [_file("pkg/__init__.py"), _file("pkg/core.py"), _file("pkg/util.py")]
    graph = ModuleGraph(files)
    assert graph.resolve_import(Import(file="pkg/core.py", module="pkg.util", names=["x"], line=1)) == "pkg.util"
    assert graph.resolve_import(Import(file="pkg/core.py", module="pkg", names=["x"], line=1)) == "pkg"


def test_external_import_unresolved():
    graph = ModuleGraph([_file("app.py")])
    assert graph.resolve_import(Import(file="app.py", module="os", names=["sep"], line=1)) is None
    assert graph.resolve_import(Import(file="app.py", module="requests.sessions", names=["Session"], line=1)) is None


def test_relative_import_level1():
    files = [_file("pkg/__init__.py"), _file("pkg/core.py"), _file("pkg/util.py")]
    graph = ModuleGraph(files)
    imp = Import(file="pkg/core.py", module="util", names=["h"], line=3, is_relative=True, level=1)
    assert graph.resolve_import(imp) == "pkg.util"


def test_relative_import_in_init():
    files = [_file("pkg/__init__.py"), _file("pkg/sub/__init__.py"), _file("pkg/sub/leaf.py")]
    graph = ModuleGraph(files)
    imp = Import(file="pkg/sub/__init__.py", module="leaf", names=["l"], line=1, is_relative=True, level=1)
    assert graph.resolve_import(imp) == "pkg.sub.leaf"


def test_dependencies_dedup_and_sort():
    files = [_file("pkg/__init__.py"), _file("pkg/a.py"), _file("pkg/b.py")]
    imports = [
        Import(file="pkg/a.py", module="pkg.b", names=["x"], line=1),
        Import(file="pkg/a.py", module="pkg.b", names=["y"], line=2),
        Import(file="pkg/a.py", module="pkg", names=["pkg"], line=3),
    ]
    deps = ModuleGraph(files).dependencies(imports)
    assert deps == {"pkg.a": ["pkg", "pkg.b"]}


def test_self_import_ignored():
    files = [_file("pkg/a.py")]
    imports = [Import(file="pkg/a.py", module="pkg.a", names=["a"], line=1)]
    assert ModuleGraph(files).dependencies(imports) == {}
