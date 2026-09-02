"""Parsers subpackage.

Python remains the primary built-in parser. JavaScript is available through
an optional tree-sitter backend so the analyzer can extend to a second
language without changing the rest of the pipeline.
"""

from .javascript_parser import JavaScriptParser, javascript_backend_available
from .python_parser import PythonParser, parse_python_file


def parser_for(language: str, rel_path: str):
    if language == "python":
        return PythonParser(rel_path)
    if language == "javascript" and javascript_backend_available():
        return JavaScriptParser(rel_path)
    return None


__all__ = ["JavaScriptParser", "PythonParser", "parse_python_file", "parser_for"]
