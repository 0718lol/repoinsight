"""Git integration: file hotspots (churn x complexity) and diff stats."""

from __future__ import annotations

import subprocess
from typing import Dict, List, Optional


def _run_git(root: str, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", root, *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_hotspots(root: str, since: Optional[str] = None) -> Dict[str, Dict]:
    """Per-file commit counts and last-touch timestamp.

    Returns {path: {"commits": int, "last_commit_ts": int, "authors": [...]}}
    or {} when git is unavailable or root is not a repository.
    """
    args = ["log", "--name-only", "--pretty=format:@@@%H|%at|%an"]
    if since:
        args.append(f"--since={since}")
    out = _run_git(root, *args)
    if out is None:
        return {}

    hotspots: Dict[str, Dict] = {}
    last_meta: Optional[tuple] = None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("@@@"):
            _, ts, author = line[3:].split("|", 2)
            last_meta = (int(ts), author)
            continue
        if last_meta is None or not line:
            continue
        ts, author = last_meta
        entry = hotspots.setdefault(
            line, {"commits": 0, "last_commit_ts": 0, "authors": set()}
        )
        entry["commits"] += 1
        entry["last_commit_ts"] = max(entry["last_commit_ts"], ts)
        entry["authors"].add(author)

    for entry in hotspots.values():
        entry["authors"] = sorted(entry["authors"])
    return hotspots


def combine_hotspots(
    file_metrics: List[Dict],
    hotspots: Dict[str, Dict],
    weight_churn: float = 0.6,
    weight_complexity: float = 0.4,
) -> List[Dict]:
    """Join LOC metrics with git churn into one ranked hotspot list.

    score = 0.6 * normalized_commits + 0.4 * normalized_code_lines.
    Files without git history score on code size alone.
    """
    max_commits = max((h["commits"] for h in hotspots.values()), default=0) or 1
    max_code = max((row.get("code", 0) for row in file_metrics), default=0) or 1

    rows: List[Dict] = []
    for row in file_metrics:
        path = row["path"]
        info = hotspots.get(path)
        commits = info["commits"] if info else 0
        score = (
            weight_churn * (commits / max_commits)
            + weight_complexity * (row.get("code", 0) / max_code)
        )
        merged = dict(row)
        merged["commits"] = commits
        merged["score"] = round(score, 4)
        rows.append(merged)
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def diff_stats(root: str, ref_a: str, ref_b: Optional[str] = None) -> Dict:
    """Added/deleted line counts between two refs (or working tree)."""
    args = ["diff", "--numstat", ref_a]
    if ref_b:
        args.append(ref_b)
    out = _run_git(root, *args)
    if out is None:
        return {}

    added = deleted = files_changed = 0
    per_file: Dict[str, Dict[str, int]] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3 or parts[0] == "-":   # binary file
            continue
        a, d, path = int(parts[0]), int(parts[1]), parts[2]
        added += a
        deleted += d
        files_changed += 1
        per_file[path] = {"added": a, "deleted": d}
    return {
        "added": added,
        "deleted": deleted,
        "files_changed": files_changed,
        "per_file": per_file,
    }
