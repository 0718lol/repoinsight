"""Tests for the optional JavaScript tree-sitter parser."""

from conftest import SRC  # noqa: F401  (sys.path setup)

import pytest

from repoinsight.analyzer import RepoAnalyzer
from repoinsight.parsers.javascript_parser import JavaScriptParser


def _require_backend() -> None:
    try:
        import tree_sitter_languages  # noqa: F401
        return
    except ImportError:
        pytest.importorskip("tree_sitter_language_pack")


JS_SOURCE = """import foo, {bar as baz, qux} from 'pkg';

class Counter {
  inc() {
    if (foo) {
      return this.dec();
    }
    return baz();
  }

  dec() {
    return qux();
  }
}

export function run() {
  return foo ? qux() : baz();
}
"""


def test_javascript_parser_extracts_symbols_and_imports():
    _require_backend()
    parser = JavaScriptParser("mod.js")
    parser.parse(JS_SOURCE)

    names = {(s.qualified_name, s.kind) for s in parser.symbols}
    assert ("Counter", "class") in names
    assert ("Counter.inc", "method") in names
    assert ("Counter.dec", "method") in names
    assert ("run", "function") in names

    imports = {(i.module, tuple(i.names)) for i in parser.imports}
    assert ("pkg", ("foo", "baz", "qux")) in imports

    inc = next(s for s in parser.symbols if s.qualified_name == "Counter.inc")
    assert "this.dec" in inc.calls
    assert inc.complexity >= 2


def test_analyzer_can_include_javascript_files(tmp_path):
    _require_backend()
    (tmp_path / "app.js").write_text(JS_SOURCE, encoding="utf-8")

    analysis = RepoAnalyzer(str(tmp_path)).analyze()
    names = {s.qualified_name for s in analysis.symbols}
    assert "app.Counter" in names
    assert "app.Counter.inc" in names
    assert ("app.Counter.inc", "app.Counter.dec") in set(analysis.call_edges)
    assert len(analysis.files) == 1
