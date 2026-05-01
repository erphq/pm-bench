"""Schema validation for the checked-in leaderboard files."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pm_bench.leaderboard_schema import validate_board

REPO_ROOT = Path(__file__).resolve().parent.parent
ALL_BOARDS = sorted((REPO_ROOT / "leaderboard").glob("*/*.json"))


@pytest.mark.parametrize("path", ALL_BOARDS, ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_every_board_passes_schema(path: Path) -> None:
    raw = json.loads(path.read_text())
    errors = validate_board(raw)
    assert errors == [], f"{path.relative_to(REPO_ROOT)}: {errors}"


def test_missing_top_key_is_caught() -> None:
    bad = {"task": "next-event", "dataset": "x", "entries": []}
    errors = validate_board(bad)
    assert any("metric" in e for e in errors)
    assert any("scored_with" in e for e in errors)
    assert any("split" in e for e in errors)


def test_unknown_task_is_caught() -> None:
    bad = {
        "task": "telekinesis",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [],
    }
    errors = validate_board(bad)
    assert any("unknown task" in e for e in errors)


def test_entry_missing_score_is_caught() -> None:
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [{"model": "m", "version": "1", "predictions_path": "p"}],
    }
    errors = validate_board(bad)
    assert any("score" in e for e in errors)


def test_entry_score_must_be_dict() -> None:
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {"model": "m", "version": "1", "predictions_path": "p", "score": 0.9}
        ],
    }
    errors = validate_board(bad)
    assert any("score" in e and "object" in e for e in errors)
