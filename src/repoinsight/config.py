"""Project configuration file support (.repoinsight.json).

Drop a `.repoinsight.json` in the project root (or pass --config) and every
repoinsight command picks it up. Recognized keys, all optional:

    {
      "ignore": ["docs", "scratch"],              // extra dirs to skip
      "forbidden_edges": [["ui.*", "core.*"]],    // layer rules for lint
      "entrypoints": ["handle_*"],                // extra dead-code exempt names
      "min_score": 70                             // score gate threshold
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

CONFIG_FILENAME = ".repoinsight.json"

_DEFAULTS: Dict = {
    "ignore": [],
    "forbidden_edges": [],
    "entrypoints": [],
    "min_score": None,
}


def load_config(root: str, explicit_path: str = None) -> Dict:
    """Load and validate config; returns a fully-populated dict.

    Precedence: explicit_path (from --config) wins, otherwise we look for
    .repoinsight.json in the analyzed root. Missing file -> defaults.
    """
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise RuntimeError(f"错误:指定的配置文件不存在:{path}")
    else:
        path = Path(root) / CONFIG_FILENAME
        if not path.exists():
            return dict(_DEFAULTS)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"配置文件格式错误:{path}({exc})") from exc
    if not isinstance(raw, dict):
        raise RuntimeError(f"配置文件格式错误:{path}(顶层必须是 JSON 对象)")

    cfg = dict(_DEFAULTS)
    if "ignore" in raw:
        cfg["ignore"] = _string_list(raw["ignore"], "ignore", path)
    if "entrypoints" in raw:
        cfg["entrypoints"] = _string_list(raw["entrypoints"], "entrypoints", path)
    if "forbidden_edges" in raw:
        edges = raw["forbidden_edges"]
        if not isinstance(edges, list) or not all(
            isinstance(e, list) and len(e) == 2 for e in edges
        ):
            raise RuntimeError(
                f"配置文件格式错误:{path}(forbidden_edges 必须是 [[A, B], ...] 形式)"
            )
        cfg["forbidden_edges"] = edges
    if "min_score" in raw and raw["min_score"] is not None:
        v = raw["min_score"]
        if not isinstance(v, int) or not 0 <= v <= 100:
            raise RuntimeError(
                f"配置文件格式错误:{path}(min_score 必须是 0-100 的整数)"
            )
        cfg["min_score"] = v
    return cfg


def _string_list(value, key: str, path: Path) -> list:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise RuntimeError(f"配置文件格式错误:{path}({key} 必须是字符串数组)")
    return value
