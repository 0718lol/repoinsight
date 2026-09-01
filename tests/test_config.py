"""Tests for config file loading and the score gate."""

import json

import pytest

from conftest import SRC  # noqa: F401

from repoinsight.cli import main
from repoinsight.config import CONFIG_FILENAME, load_config


def test_missing_config_returns_defaults(tmp_path):
    cfg = load_config(str(tmp_path))
    assert cfg == {"ignore": [], "forbidden_edges": [],
                   "entrypoints": [], "min_score": None}


def test_load_and_validate_full_config(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text(json.dumps({
        "ignore": ["docs"],
        "forbidden_edges": [["ui.*", "core.*"]],
        "entrypoints": ["handle_*"],
        "min_score": 70,
    }), encoding="utf-8")
    cfg = load_config(str(tmp_path))
    assert cfg["ignore"] == ["docs"]
    assert cfg["forbidden_edges"] == [["ui.*", "core.*"]]
    assert cfg["entrypoints"] == ["handle_*"]
    assert cfg["min_score"] == 70


def test_explicit_path_wins(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text('{"min_score": 50}', encoding="utf-8")
    other = tmp_path / "other.json"
    other.write_text('{"min_score": 90}', encoding="utf-8")
    assert load_config(str(tmp_path), str(other))["min_score"] == 90


def test_missing_explicit_config_errors(tmp_path):
    with pytest.raises(RuntimeError) as ei:
        load_config(str(tmp_path), str(tmp_path / "nope.json"))
    assert "不存在" in str(ei.value)


def test_malformed_json_chinese_error(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text("{bad json", encoding="utf-8")
    with pytest.raises(RuntimeError) as ei:
        load_config(str(tmp_path))
    assert "格式错误" in str(ei.value)


def test_bad_min_score_rejected(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text('{"min_score": 999}', encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_config(str(tmp_path))


def test_bad_forbidden_edges_rejected(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text('{"forbidden_edges": ["x"]}', encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_config(str(tmp_path))


# ---------------- score gate through the real CLI -------------------
def test_score_gate_fails_on_high_threshold(sample_repo):
    rc = main(["score", str(sample_repo), "--min", "100"])
    assert rc == 1


def test_score_gate_passes_on_low_threshold(sample_repo):
    rc = main(["score", str(sample_repo), "--min", "1"])
    assert rc == 0


def test_min_score_from_config_file(sample_repo):
    (sample_repo / CONFIG_FILENAME).write_text('{"min_score": 100}', encoding="utf-8")
    rc = main(["score", str(sample_repo)])
    assert rc == 1


def test_config_ignore_removes_files(sample_repo, tmp_path, capsys):
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text('{"ignore": ["subdir"]}', encoding="utf-8")
    out = tmp_path / "out.json"
    rc = main(["--config", str(cfg_path), "json", str(sample_repo), "-o", str(out)])
    assert rc == 0
    paths = [f["path"] for f in json.loads(out.read_text(encoding="utf-8"))["analysis"]["files"]]
    assert "subdir/data.json" not in paths
    assert "pkg/core.py" in paths


def test_config_entrypoints_silence_dead_code(analysis):
    # dead_function in the fixture is normally flagged; exempt it via patterns
    from repoinsight.lint import run_all
    before = [f for f in run_all(analysis.result) if f.kind == "dead_symbol"]
    after = [f for f in run_all(analysis.result, entrypoints=["dead_*"])
             if f.kind == "dead_symbol"]
    assert len(after) == len(before) - 1
    assert not any("dead_function" in f.message for f in after)
