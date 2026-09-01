"""Shared fixtures: build a small sample repository on the fly."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from repoinsight.analyzer import RepoAnalyzer  # noqa: E402

SAMPLE_REPO = {
    "pkg/__init__.py": "",
    "pkg/core.py": '''"""Core module."""
import os
from pkg.helpers import helper_used, helper_unused_by_others
from pkg import missing_name


class Engine:
    """An engine."""

    def __init__(self):
        self.started = False

    def start(self):
        self.started = True
        return helper_used()

    def stop(self):
        self.started = False

    def complex_logic(self, values):
        total = 0
        for v in values:
            if v > 0:
                total += v
            elif v < -5:
                total -= 1
            else:
                continue
        while total > 100:
            total = total // 2
        return total


def entrypoint():
    engine = Engine()
    engine.start()
    return engine


def dead_function():
    return os.sep
''',
    "pkg/helpers.py": '''"""Helpers."""
from pkg.core import Engine


def helper_used():
    return 42


def helper_unused_by_others():
    return Engine
''',
    "pkg/cyclic_a.py": '''"""Cyclic A."""
from pkg import cyclic_b


def fa():
    return cyclic_b.fb()
''',
    "pkg/cyclic_b.py": '''"""Cyclic B."""
from pkg import cyclic_a


def fb():
    return cyclic_a.fa()
''',
    "pkg/deep.py": '''"""Deep call chain."""
from pkg.helpers import helper_used


def level1():
    return level2()


def level2():
    return level3()


def level3():
    return helper_used()
''',
    "app.py": '''"""Entry point."""
from pkg.deep import level1


def main():
    return level1()
''',
    "notes.md": "# notes\n\nplain markdown\n",
    "subdir/data.json": '{"k": 1}\n',
}


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    root = tmp_path / "sample_repo"
    for rel, content in SAMPLE_REPO.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


@pytest.fixture
def analysis(sample_repo: Path):
    analyzer = RepoAnalyzer(str(sample_repo))
    analyzer.analyze()
    return analyzer
