"""Tests for health + compare modules."""

import subprocess

import pytest

from conftest import SRC  # noqa: F401

from repoinsight.compare import compare_refs, diff_analyses, render_diff_text
from repoinsight.analyzer import RepoAnalyzer


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True, text=True)


@pytest.fixture
def evolving_repo(tmp_path):
    """Git repo with two commits: v1 simple, v2 adds a module and a function."""
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except OSError:
        pytest.skip("git not available")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "core.py").write_text(
        "def calc(x):\n"
        "    if x > 0:\n"
        "        return x\n"
        "    return 0\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=A", "-c", "user.email=a@x", "commit", "-qm", "v1")

    pkg = root / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "helpers.py").write_text(
        "from core import calc\n\n"
        "def wrap(x):\n"
        "    return calc(x) + 1\n", encoding="utf-8")
    (root / "core.py").write_text(
        "def calc(x):\n"
        "    if x > 0:\n"
        "        for i in range(x):\n"
        "            if i % 2:\n"
        "                x += i\n"
        "        return x\n"
        "    return 0\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=A", "-c", "user.email=a@x", "commit", "-qm", "v2")
    return root


def test_compare_refs_detects_changes(evolving_repo):
    d = compare_refs(str(evolving_repo), "HEAD~1", "HEAD")
    assert d.files_added == ["pkg/__init__.py", "pkg/helpers.py"]
    assert d.files_removed == []
    assert "pkg.helpers.wrap" in d.symbols_added
    assert d.symbols_removed == []
    assert d.edges_added == [("pkg.helpers.wrap", "core.calc")]
    up = dict((n, (b, a)) for n, b, a in d.complexity_up)
    assert up["core.calc"] == (2, 4)  # if + for + if -> cx grows 2 -> 4


def test_compare_refs_no_change(tmp_path):
    root = tmp_path / "flat"
    root.mkdir()
    (root / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=A", "-c", "user.email=a@x", "commit", "-qm", "one")
    d = compare_refs(str(root), "HEAD", "HEAD")
    assert d.files_added == [] and d.symbols_added == []
    assert d.edges_added == [] and d.complexity_up == []


def test_compare_refs_bad_ref(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    _git(root, "init", "-q")
    with pytest.raises(RuntimeError):
        compare_refs(str(root), "HEAD", "no-such-ref")


def test_render_diff_text_chinese(evolving_repo):
    d = compare_refs(str(evolving_repo), "HEAD~1", "HEAD")
    text = render_diff_text(d)
    assert "架构对比" in text
    assert "新增" in text and "复杂度" in text


def test_diff_analyses_direct(sample_repo, tmp_path):
    a = RepoAnalyzer(str(sample_repo))
    a.analyze()
    b = RepoAnalyzer(str(sample_repo))
    b.analyze()
    d = diff_analyses(a, b)
    assert d.symbols_added == [] and d.symbols_removed == []
