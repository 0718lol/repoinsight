"""Tests for the interactive report."""

from conftest import SRC  # noqa: F401

from repoinsight.report.interactive import render_interactive_report


def test_renders_self_contained_html(tmp_path, analysis):
    out = tmp_path / "interactive.html"
    render_interactive_report(analysis, str(out))
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    # embedded data blob and script are present
    assert 'id="ri-data"' in html
    # unique element ids (two graphs must not share ids)
    assert 'id="svg-deps"' in html and 'id="svg-calls"' in html
    assert 'id="detail-deps"' in html and 'id="detail-calls"' in html
    # five tabs
    for tab in ("deps", "calls", "src", "cx", "coupling"):
        assert f'data-tab="{tab}"' in html


def test_no_external_references(tmp_path, analysis):
    out = tmp_path / "interactive.html"
    render_interactive_report(analysis, str(out))
    html = out.read_text(encoding="utf-8")
    # The SVG namespace string is a DOM constant, never fetched.
    html = html.replace("http://www.w3.org/2000/svg", "")
    assert "http://" not in html
    assert "https://" not in html
    assert "src=" not in html
    assert "<link" not in html


def test_embeds_sources_and_symbols(tmp_path, analysis):
    out = tmp_path / "interactive.html"
    render_interactive_report(analysis, str(out))
    html = out.read_text(encoding="utf-8")
    assert "pkg/core.py" in html          # file entry
    assert "Engine" in html               # symbol / source content
    assert '"moduleDeps"' in html         # data blob keys


def test_renders_reasonable_size(tmp_path, analysis):
    out = tmp_path / "interactive.html"
    render_interactive_report(analysis, str(out))
    size = out.stat().st_size
    assert size < 3 * 1024 * 1024
    assert size > 10_000  # non-trivial content


def test_json_blob_parses(tmp_path, analysis):
    import json
    out = tmp_path / "interactive.html"
    render_interactive_report(analysis, str(out))
    html = out.read_text(encoding="utf-8")
    blob = html.split('id="ri-data" type="application/json">', 1)[1]
    blob = blob.split("</script>", 1)[0]
    data = json.loads(blob.replace("<\\/", "</"))
    assert data["summary"]["python_files"] == 7
    assert "pkg.cyclic_b" in data["moduleDeps"]["pkg.cyclic_a"]
