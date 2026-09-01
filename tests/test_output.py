"""Tests for output writers and the HTML report."""

import json

from conftest import SRC  # noqa: F401

from repoinsight.output import (
    write_call_dot,
    write_json,
    write_module_dot,
    write_summary_text,
)
from repoinsight.report import render_html_report


def test_write_json(tmp_path, analysis):
    out = tmp_path / "out.json"
    write_json(analysis, str(out))
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary"]["python_files"] == 7
    assert "symbols" in payload["analysis"]


def test_write_module_dot(tmp_path, analysis):
    out = tmp_path / "modules.dot"
    write_module_dot(analysis, str(out))
    text = out.read_text(encoding="utf-8")
    assert text.startswith("digraph module_dependencies")
    assert '"pkg.cyclic_a" -> "pkg.cyclic_b"' in text
    assert "digraph" and "rankdir" in text


def test_write_call_dot_limited(tmp_path, analysis):
    out = tmp_path / "calls.dot"
    write_call_dot(analysis, str(out), max_nodes=3)
    text = out.read_text(encoding="utf-8")
    assert text.startswith("digraph call_graph")
    # at most 3 node declarations
    body = text.split("{", 1)[1]
    node_count = sum(1 for line in body.splitlines()
                     if line.strip().startswith('"') and line.strip().endswith('";')
                     and "->" not in line)
    assert node_count <= 3


def test_write_summary_text(tmp_path, analysis):
    out = tmp_path / "summary.txt"
    write_summary_text(analysis, str(out))
    text = out.read_text(encoding="utf-8")
    assert "REPOINSIGHT 代码库分析摘要" in text
    assert "pkg/core.py" in text


def test_summary_text_stdout(analysis):
    text = write_summary_text(analysis, None)
    assert "复杂度最高的函数" in text


def test_html_report_is_self_contained(tmp_path, analysis):
    out = tmp_path / "report.html"
    render_html_report(analysis, str(out))
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "<script" in html and "<style" in html
    # no external asset references
    assert "http://" not in html and "https://" not in html
    assert "src=" not in html and 'href="' not in html
    # key sections present
    for marker in ("tab-files", "tab-complexity", "tab-coupling", "tab-symbols", "tab-data"):
        assert marker in html
