"""Tests for the Python AST parser."""

from conftest import SRC  # noqa: F401  (sys.path setup)

from repoinsight.parsers.python_parser import PythonParser

CORE_SOURCE = '''import os
from typing import List
from . import sibling
from .util import helper


class Base:
    def base_method(self):
        return 1


class Child(Base):
    def child_method(self):
        return self.base_method()

    async def async_thing(self):
        return [x for x in range(3)]


def branchy(a, b):
    if a and b:
        return 1
    elif a:
        return 2
    try:
        for i in range(3):
            while i:
                i -= 1
    except ValueError:
        pass
    return 0
'''


def _parse(src: str, name: str = "mod.py"):
    parser = PythonParser(name)
    parser.parse(src)
    return parser


def test_symbols_extracted():
    parser = _parse(CORE_SOURCE)
    kinds = {(s.qualified_name, s.kind) for s in parser.symbols}
    assert ("Base", "class") in kinds
    assert ("Child", "class") in kinds
    assert ("Child.child_method", "method") in kinds
    assert ("Child.async_thing", "async_function") in kinds
    assert ("branchy", "function") in kinds


def test_nested_class_method_qualified():
    src = "class Outer:\n    class Inner:\n        def m(self):\n            pass\n"
    parser = _parse(src)
    names = {s.qualified_name for s in parser.symbols}
    assert "Outer.Inner" in names
    assert "Outer.Inner.m" in names
    method = next(s for s in parser.symbols if s.qualified_name == "Outer.Inner.m")
    assert method.parent == "Outer.Inner"


def test_class_bases_and_decorators():
    parser = _parse(CORE_SOURCE)
    child = next(s for s in parser.symbols if s.qualified_name == "Child")
    assert child.bases == ["Base"]

    src = "@staticmethod\n@lru_cache(maxsize=8)\ndef f():\n    pass\n"
    parser = _parse(src)
    f = parser.symbols[0]
    assert f.decorators == ["staticmethod", "lru_cache"]


def test_calls_collected():
    parser = _parse(CORE_SOURCE)
    method = next(s for s in parser.symbols if s.qualified_name == "Child.child_method")
    assert "self.base_method" in method.calls


def test_complexity_counts_branches():
    parser = _parse(CORE_SOURCE)
    branchy = next(s for s in parser.symbols if s.qualified_name == "branchy")
    # if(1) + and(1) + elif(1) + except(1) + for(1) + while(1) = 6, cx = 7
    assert branchy.complexity == 7
    base = next(s for s in parser.symbols if s.qualified_name == "Base.base_method")
    assert base.complexity == 1


def test_imports_absolute_and_relative():
    parser = _parse(CORE_SOURCE)
    modules = {(i.module, i.is_relative, i.level) for i in parser.imports}
    assert ("os", False, 0) in modules
    assert ("typing", False, 0) in modules
    assert ("", True, 1) in modules
    assert ("util", True, 1) in modules


def test_line_spans():
    parser = _parse(CORE_SOURCE)
    child = next(s for s in parser.symbols if s.qualified_name == "Child")
    assert child.line_start < child.line_end
    assert child.line_start == CORE_SOURCE.split("class Child")[0].count("\n") + 1


def test_syntax_error_raises_value_error():
    parser = PythonParser("bad.py")
    try:
        parser.parse("def broken(:\n    pass\n")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for syntax error")
