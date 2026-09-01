"""Parsers subpackage. Python is fully supported; other languages are stubs."""

from .python_parser import PythonParser, parse_python_file

__all__ = ["PythonParser", "parse_python_file"]
