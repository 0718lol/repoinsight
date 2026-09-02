"""Tests for scanner: discovery, language detection, line counting."""

from pathlib import Path

from repoinsight.scanner import RepoScanner, count_lines, detect_language


def test_detect_language_by_suffix(tmp_path: Path):
    assert detect_language(tmp_path / "a.py") == "python"
    assert detect_language(tmp_path / "a.ts") == "typescript"
    assert detect_language(tmp_path / "a.go") == "go"
    assert detect_language(tmp_path / "a.weird") == "unknown"


def test_count_lines_categories(tmp_path: Path):
    f = tmp_path / "x.py"
    f.write_text("# comment\n\ncode = 1\n    indented = 2\n", encoding="utf-8")
    total, code, comment, blank = count_lines(f, "python")
    assert (total, code, comment, blank) == (4, 2, 1, 1)


def test_count_lines_handles_binary(tmp_path: Path):
    f = tmp_path / "blob.py"
    f.write_bytes(b"\xff\xfe\x00broken")
    total, *_ = count_lines(f, "python")
    assert total >= 0  # must not raise


def test_scanner_finds_files_and_ignores(sample_repo: Path):
    scanner = RepoScanner(str(sample_repo))
    files = scanner.scan()
    paths = {f.path for f in files}
    assert "pkg/core.py" in paths
    assert "notes.md" in paths
    assert "subdir/data.json" in paths


def test_scanner_ignores_default_dirs(sample_repo: Path):
    (sample_repo / "__pycache__").mkdir(exist_ok=True)
    (sample_repo / "__pycache__" / "junk.py").write_text("x = 1\n", encoding="utf-8")
    (sample_repo / "node_modules").mkdir(exist_ok=True)
    (sample_repo / "node_modules" / "junk.js").write_text("var x;", encoding="utf-8")
    scanner = RepoScanner(str(sample_repo))
    paths = {f.path for f in scanner.scan()}
    assert not any("__pycache__" in p for p in paths)
    assert not any("node_modules" in p for p in paths)


def test_scanner_extra_ignore(sample_repo: Path):
    scanner = RepoScanner(str(sample_repo), ignored_dirs=["subdir"])
    paths = {f.path for f in scanner.scan()}
    assert "subdir/data.json" not in paths


def test_scanner_relative_paths_are_posix(sample_repo: Path):
    scanner = RepoScanner(str(sample_repo))
    for f in scanner.scan():
        assert "\\" not in f.path
        assert not f.path.startswith("/")
