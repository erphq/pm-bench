"""Tests for `pm-bench validate`."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from pm_bench.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
GOOD_BOARD = REPO_ROOT / "leaderboard" / "next-event" / "synthetic-toy.json"


def test_validate_clean_board_succeeds() -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["validate", str(GOOD_BOARD), "--repo-root", str(REPO_ROOT)])
    assert r.exit_code == 0, r.output
    assert "schema + scores OK" in r.output


def test_validate_no_rescore_skips_score_check() -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["validate", str(GOOD_BOARD), "--no-rescore"])
    assert r.exit_code == 0, r.output
    assert "schema OK" in r.output
    assert "scores" not in r.output  # the --no-rescore message omits "scores"


def test_validate_catches_schema_errors(tmp_path: Path) -> None:
    bad = {
        "task": "telekinesis",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [],
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    runner = CliRunner()
    r = runner.invoke(main, ["validate", str(p), "--no-rescore"])
    assert r.exit_code == 2
    assert "unknown task" in r.output


def test_validate_catches_score_drift(tmp_path: Path) -> None:
    raw = json.loads(GOOD_BOARD.read_text())
    raw["entries"][0]["score"]["top1"] = 0.111
    p = tmp_path / "drift.json"
    p.write_text(json.dumps(raw))
    runner = CliRunner()
    r = runner.invoke(main, ["validate", str(p), "--repo-root", str(REPO_ROOT)])
    assert r.exit_code == 2
    assert "drift" in r.output
