"""Repository scanning: file discovery, language detection, line counting."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Set

from .models import SourceFile

# Languages we can at least recognize (line counting) even if we cannot
# fully parse them. Parsing support is a separate concern (see parsers/).
LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".rb": "ruby",
    ".sh": "shell",
    ".bash": "shell",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".html": "html",
    ".css": "css",
}

# Default ignore rules: directory names and file-glob-ish patterns.
DEFAULT_IGNORED_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "node_modules", "venv", ".venv", "env", ".env",
    "dist", "build", ".tox", ".eggs", "target", ".idea", ".vscode",
}

# Comment prefixes used for the code/comment/blank line split.
COMMENT_PREFIXES = {
    "python": ("#",),
    "javascript": ("//", "/*", "*"),
    "typescript": ("//", "/*", "*"),
    "go": ("//",),
    "rust": ("//",),
    "java": ("//", "/*", "*"),
    "c": ("//", "/*", "*"),
    "cpp": ("//", "/*", "*"),
    "ruby": ("#",),
    "shell": ("#",),
}


def detect_language(path: Path) -> str:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "unknown")


def count_lines(path: Path, language: str) -> "tuple[int, int, int, int]":
    """Return (total, code, comment, blank) line counts."""
    prefixes = COMMENT_PREFIXES.get(language, ("#", "//"))
    total = code = comment = blank = 0
    try:
        with path.open("rb") as fh:
            raw = fh.read()
    except OSError:
        return 0, 0, 0, 0
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    for line in text.splitlines():
        total += 1
        stripped = line.strip()
        if not stripped:
            blank += 1
        elif any(stripped.startswith(p) for p in prefixes):
            comment += 1
        else:
            code += 1
    return total, code, comment, blank


class RepoScanner:
    """Walk a repository and produce SourceFile records."""

    def __init__(
        self,
        root: str,
        ignored_dirs: Iterable[str] = (),
        ignored_files: Iterable[str] = (),
        max_file_size: int = 2 * 1024 * 1024,
    ):
        self.root = Path(root).resolve()
        self.ignored_dirs: Set[str] = set(DEFAULT_IGNORED_DIRS) | set(ignored_dirs)
        self.ignored_files: Set[str] = set(ignored_files)
        self.max_file_size = max_file_size

    def scan(self) -> List[SourceFile]:
        files: List[SourceFile] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(
                d for d in dirnames if d not in self.ignored_dirs
            )
            for name in sorted(filenames):
                if name in self.ignored_files or name.startswith("."):
                    continue
                full = Path(dirpath) / name
                try:
                    if full.stat().st_size > self.max_file_size:
                        continue
                except OSError:
                    continue
                rel = full.relative_to(self.root).as_posix()
                language = detect_language(full)
                total, code, comment, blank = count_lines(full, language)
                files.append(
                    SourceFile(
                        path=rel,
                        absolute_path=str(full),
                        language=language,
                        lines_total=total,
                        lines_code=code,
                        lines_comment=comment,
                        lines_blank=blank,
                    )
                )
        return files
