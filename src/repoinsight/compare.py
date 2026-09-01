"""Compare two git refs: what changed in the architecture between them.

Strategy: `git archive <ref>` each ref into a temp dir, run the normal
analyzer on both trees, then diff symbols / complexity / dependency edges.
No checkout of the working tree is touched.
"""

from __future__ import annotations

import subprocess
import tempfile
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .analyzer import RepoAnalyzer


def _run(root: str, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(["git", "-C", root, *args],
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _export_ref(root: str, ref: str, dest: Path) -> bool:
    """Extract a ref's tree into dest using git archive | tar -x."""
    git_proc = subprocess.run(
        ["git", "-C", root, "archive", "--format=tar", ref],
        capture_output=True, timeout=120,
    )
    if git_proc.returncode != 0:
        return False
    tar_proc = subprocess.run(
        ["tar", "-x", "-C", str(dest)],
        input=git_proc.stdout, capture_output=True, timeout=120,
    )
    return tar_proc.returncode == 0


@dataclass
class RefDiff:
    ref_a: str
    ref_b: str
    files_added: List[str] = field(default_factory=list)
    files_removed: List[str] = field(default_factory=list)
    symbols_added: List[str] = field(default_factory=list)
    symbols_removed: List[str] = field(default_factory=list)
    edges_added: List[Tuple[str, str]] = field(default_factory=list)
    edges_removed: List[Tuple[str, str]] = field(default_factory=list)
    complexity_up: List[Tuple[str, int, int]] = field(default_factory=list)  # name, before, after
    complexity_down: List[Tuple[str, int, int]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "ref_a": self.ref_a, "ref_b": self.ref_b,
            "files_added": self.files_added, "files_removed": self.files_removed,
            "symbols_added": self.symbols_added, "symbols_removed": self.symbols_removed,
            "edges_added": [list(e) for e in self.edges_added],
            "edges_removed": [list(e) for e in self.edges_removed],
            "complexity_up": [list(t) for t in self.complexity_up],
            "complexity_down": [list(t) for t in self.complexity_down],
        }


def compare_refs(root: str, ref_a: str, ref_b: str) -> RefDiff:
    """Analyze two refs and return the architecture diff between them.

    The whole repository tree (repo toplevel) is exported for each ref, so
    paths in the diff are repo-root-relative regardless of which
    subdirectory was passed in.
    """
    root = str(Path(root).resolve())
    toplevel = (_run(root, "rev-parse", "--show-toplevel") or "").strip() or root
    tmp = Path(tempfile.mkdtemp(prefix="repoinsight-diff-"))
    try:
        dir_a, dir_b = tmp / "a", tmp / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        if not _export_ref(toplevel, ref_a, dir_a):
            raise RuntimeError(f"无法导出 {ref_a}(它存在吗?该目录是 git 仓库吗?)")
        if not _export_ref(toplevel, ref_b, dir_b):
            raise RuntimeError(f"无法导出 {ref_b}")

        ana_a = RepoAnalyzer(str(dir_a))
        ana_a.analyze()
        ana_b = RepoAnalyzer(str(dir_b))
        ana_b.analyze()
        return diff_analyses(ana_a, ana_b, ref_a=ref_a, ref_b=ref_b)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def diff_analyses(a: RepoAnalyzer, b: RepoAnalyzer,
                  ref_a: str = "A", ref_b: str = "B") -> RefDiff:
    """Diff two already-analyzed trees (files relative paths must be comparable)."""
    d = RefDiff(ref_a=ref_a, ref_b=ref_b)

    files_a = {f.path for f in a.result.files if f.language == "python"}
    files_b = {f.path for f in b.result.files if f.language == "python"}
    d.files_added = sorted(files_b - files_a)
    d.files_removed = sorted(files_a - files_b)

    def qmap(analyzer: RepoAnalyzer) -> Dict[str, int]:
        return {s.qualified_name: s.complexity
                for s in analyzer.result.symbols if s.is_function_like}

    cx_a, cx_b = qmap(a), qmap(b)
    d.symbols_added = sorted(set(cx_b) - set(cx_a))
    d.symbols_removed = sorted(set(cx_a) - set(cx_b))
    for name in set(cx_a) & set(cx_b):
        if cx_b[name] > cx_a[name]:
            d.complexity_up.append((name, cx_a[name], cx_b[name]))
        elif cx_b[name] < cx_a[name]:
            d.complexity_down.append((name, cx_a[name], cx_b[name]))
    d.complexity_up.sort(key=lambda t: -(t[2] - t[1]))
    d.complexity_down.sort(key=lambda t: -(t[1] - t[2]))

    edges_a = set(a.result.call_edges)
    edges_b = set(b.result.call_edges)
    d.edges_added = sorted(edges_b - edges_a)
    d.edges_removed = sorted(edges_a - edges_b)
    return d


def render_diff_text(d: RefDiff, limit: int = 12) -> str:
    """Chinese text summary of a RefDiff."""
    out = [f"架构对比:{d.ref_a} → {d.ref_b}", "=" * 60]

    out.append(f"文件:新增 {len(d.files_added)} 个,删除 {len(d.files_removed)} 个")
    for p in d.files_added[:limit]:
        out.append(f"  + {p}")
    for p in d.files_removed[:limit]:
        out.append(f"  - {p}")

    out.append(f"函数/方法:新增 {len(d.symbols_added)},删除 {len(d.symbols_removed)}")
    for s in d.symbols_added[:limit]:
        out.append(f"  + {s}")
    for s in d.symbols_removed[:limit]:
        out.append(f"  - {s}")

    out.append(f"调用关系:新增 {len(d.edges_added)} 条,消失 {len(d.edges_removed)} 条")
    for src, dst in d.edges_added[:limit]:
        out.append(f"  + {src} → {dst}")
    for src, dst in d.edges_removed[:limit]:
        out.append(f"  - {src} → {dst}")

    out.append(f"复杂度上升 {len(d.complexity_up)} 个,下降 {len(d.complexity_down)} 个")
    for name, before, after in d.complexity_up[:limit]:
        out.append(f"  ▲ {name} {before} → {after}")
    for name, before, after in d.complexity_down[:limit]:
        out.append(f"  ▼ {name} {before} → {after}")

    return "\n".join(out) + "\n"
