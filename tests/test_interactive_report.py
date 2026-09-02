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
    # The report opens on an explicit conclusion view, with analysis details
    # kept in separate tabs.
    assert 'data-tab="overview"' in html
    assert 'class="tabpage active" id="tab-overview"' in html
    assert "架构健康分" in html
    assert "当前扫描范围" in html
    for tab in ("overview", "deps", "calls", "charts", "src", "cx", "coupling"):
        assert f'data-tab="{tab}"' in html
    assert 'role="tablist"' in html
    assert 'aria-hidden="true"' in html


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


def test_package_aggregation():
    from repoinsight.report.interactive import aggregate_deps_by_package
    deps = {
        "a.core.x": ["a.core.y", "b.util.z"],
        "b.util.z": ["b.util.w", "c.thing.q"],
    }
    out = aggregate_deps_by_package(deps)
    assert out == {"a": ["b"], "b": ["c"]}  # self-package edges dropped


def test_truncation_flag_and_cap(tmp_path):
    from repoinsight.analyzer import RepoAnalyzer
    from repoinsight.report.interactive import _collect_data

    root = tmp_path / "big"
    root.mkdir()
    long_file = root / "long.py"
    long_file.write_text("\n".join(f"x{i} = {i}" for i in range(700)), encoding="utf-8")
    (root / "short.py").write_text("a = 1\n", encoding="utf-8")

    analyzer = RepoAnalyzer(str(root))
    analyzer.analyze()
    data = _collect_data(analyzer)
    assert len(data["sources"]["long.py"]) == 500
    assert data["truncatedFiles"]["long.py"] == 700
    assert "short.py" not in data["truncatedFiles"]
    assert data["graphMode"] == "module"


def test_big_repo_switches_to_package_mode(tmp_path):
    from repoinsight.analyzer import RepoAnalyzer
    from repoinsight.report.interactive import _collect_data

    root = tmp_path / "huge"
    root.mkdir()
    # 152 modules (>150 threshold) with cross-package imports
    for pkg in ("aa", "bb"):
        (root / pkg).mkdir()
        (root / pkg / "__init__.py").write_text("", encoding="utf-8")
    for i in range(152):
        pkg = "aa" if i % 2 == 0 else "bb"
        target = "bb.m1" if pkg == "aa" else "aa.m0"
        (root / pkg / f"m{i}.py").write_text(
            f"from {target} import x\n", encoding="utf-8")
    analyzer = RepoAnalyzer(str(root))
    analyzer.analyze()
    data = _collect_data(analyzer)
    assert data["graphMode"] == "package"
    assert set(data["modules"]) == {"aa", "bb"}
    assert data["moduleDeps"] == {"aa": ["bb"], "bb": ["aa"]}
