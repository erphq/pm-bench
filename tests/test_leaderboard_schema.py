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


def test_duplicate_model_names_caught() -> None:
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {"model": "same", "version": "1", "predictions_path": "p", "score": {}},
            {"model": "same", "version": "2", "predictions_path": "q", "score": {}},
        ],
    }
    errors = validate_board(bad)
    assert any("duplicate model name" in e for e in errors)


def test_model_name_with_special_chars_caught() -> None:
    """Backticks / spaces / etc. would break markdown rendering."""
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {
                "model": "has`backtick",
                "version": "1",
                "predictions_path": "p",
                "score": {},
            }
        ],
    }
    errors = validate_board(bad)
    assert any("[A-Za-z0-9._-]" in e for e in errors)


def test_absolute_predictions_path_rejected() -> None:
    """Absolute paths in predictions_path could read files outside the repo."""
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {
                "model": "x",
                "version": "1",
                "predictions_path": "/etc/passwd",
                "score": {},
            }
        ],
    }
    errors = validate_board(bad)
    assert any("absolute" in e for e in errors)


def test_split_kind_as_non_string_does_not_traceback() -> None:
    """Earlier versions raw-TypeError'd on `split.kind` being a list
    (unhashable for the `in VALID_SPLIT_KINDS` check). Now: clean error."""
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": ["case-chrono"]},  # list, not string
        "entries": [],
    }
    errors = validate_board(bad)
    assert any("must be a string" in e for e in errors)


def test_unknown_split_kind_rejected() -> None:
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "random"},
        "entries": [],
    }
    errors = validate_board(bad)
    assert any("unknown split kind" in e for e in errors)


def test_score_value_must_be_numeric() -> None:
    """`"top1": "0.5"` would crash math.isclose at verify time."""
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {
                "model": "m",
                "version": "1",
                "predictions_path": "p",
                "score": {"top1": "0.5"},
            }
        ],
    }
    errors = validate_board(bad)
    assert any("must be a number" in e and "top1" in e for e in errors)


def test_version_must_be_non_empty_string() -> None:
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {
                "model": "m",
                "version": 1,  # int, not string
                "predictions_path": "p",
                "score": {},
            }
        ],
    }
    errors = validate_board(bad)
    assert any("version" in e and "non-empty string" in e for e in errors)


def test_scored_at_when_present_must_be_string() -> None:
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {
                "model": "m",
                "version": "1",
                "predictions_path": "p",
                "score": {},
                "scored_at": 12345,  # int instead of ISO 8601 string
            }
        ],
    }
    errors = validate_board(bad)
    assert any("scored_at" in e and "string" in e for e in errors)


def test_empty_predictions_path_rejected() -> None:
    """Empty path used to pass schema and then crash inside _open_text
    with IsADirectoryError."""
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {"model": "x", "version": "1", "predictions_path": "", "score": {}}
        ],
    }
    errors = validate_board(bad)
    assert any("non-empty path" in e for e in errors)


def test_scored_at_must_include_time_component() -> None:
    """Bare date `2026-04-30` is parseable by `fromisoformat` but is
    too coarse to mark a scoring run."""
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {
                "model": "m",
                "version": "1",
                "predictions_path": "p",
                "score": {},
                "scored_at": "2026-04-30",
            }
        ],
    }
    errors = validate_board(bad)
    assert any("time component" in e for e in errors)


def test_scored_at_must_be_iso_8601() -> None:
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {
                "model": "m",
                "version": "1",
                "predictions_path": "p",
                "score": {},
                "scored_at": "yesterday",
            }
        ],
    }
    errors = validate_board(bad)
    assert any("ISO 8601" in e for e in errors)


def test_traversing_predictions_path_rejected() -> None:
    """`../` in predictions_path could escape the repo."""
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {
                "model": "x",
                "version": "1",
                "predictions_path": "../../etc/passwd",
                "score": {},
            }
        ],
    }
    errors = validate_board(bad)
    assert any("traverse" in e for e in errors)


def test_model_name_with_space_caught() -> None:
    bad = {
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [
            {
                "model": "has space",
                "version": "1",
                "predictions_path": "p",
                "score": {},
            }
        ],
    }
    errors = validate_board(bad)
    assert any("space" in e or "[A-Za-z0-9._-]" in e for e in errors)


def test_non_string_required_fields_caught() -> None:
    bad = {
        "task": "next-event",
        "dataset": None,
        "metric": "m",
        "scored_with": "z",
        "split": {"kind": "case-chrono"},
        "entries": [],
    }
    errors = validate_board(bad)
    assert any("dataset" in e and "string" in e for e in errors)


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
