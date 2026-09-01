"""Tests for git integration. Skipped entirely if git is unavailable."""

import subprocess

import pytest

from conftest import SRC  # noqa: F401  (sys.path setup)

from repoinsight.gitinfo import combine_hotspots, diff_stats, git_hotspots

GIT = True


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path):
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except OSError:
        pytest.skip("git not available")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=A", "-c", "user.email=a@x", "commit", "-qm", "one")
    (root / "a.py").write_text("x = 2\n", encoding="utf-8")
    (root / "b.py").write_text("y = 1\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=B", "-c", "user.email=b@x", "commit", "-qm", "two")
    return root


def test_hotspots_count_commits(git_repo):
    spots = git_hotspots(str(git_repo))
    assert spots["a.py"]["commits"] == 2
    assert spots["b.py"]["commits"] == 1
    assert set(spots["a.py"]["authors"]) == {"A", "B"}


def test_hotspots_non_repo_returns_empty(tmp_path):
    assert git_hotspots(str(tmp_path)) == {}


def test_combine_hotspots_ranking():
    metrics = [
        {"path": "hot.py", "code": 100, "language": "python"},
        {"path": "cold.py", "code": 10, "language": "python"},
    ]
    spots = {"hot.py": {"commits": 10, "last_commit_ts": 0, "authors": []}}
    rows = combine_hotspots(metrics, spots)
    assert rows[0]["path"] == "hot.py"
    assert rows[0]["commits"] == 10
    assert rows[0]["score"] > rows[1]["score"]


def test_combine_hotspots_no_git_data():
    metrics = [{"path": "x.py", "code": 50, "language": "python"}]
    rows = combine_hotspots(metrics, {})
    assert rows[0]["commits"] == 0
    assert rows[0]["score"] > 0


def test_diff_stats_between_commits(git_repo):
    log = subprocess.run(["git", "-C", str(git_repo), "rev-list", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.split()
    older = log[-1]
    stats = diff_stats(str(git_repo), older, "HEAD")
    assert stats["files_changed"] == 2
    assert stats["added"] == 2
    assert stats["deleted"] == 1
    assert stats["per_file"]["a.py"]["deleted"] == 1


def test_diff_stats_working_tree(git_repo):
    (git_repo / "b.py").write_text("y = 2\nnew = 3\n", encoding="utf-8")
    stats = diff_stats(str(git_repo), "HEAD")
    assert stats["per_file"]["b.py"] == {"added": 2, "deleted": 1}


def test_diff_stats_non_repo(tmp_path):
    assert diff_stats(str(tmp_path), "HEAD") == {}
