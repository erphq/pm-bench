"""Tests for `pm-bench compare` and `compare_boards`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from pm_bench.cli import main
from pm_bench.leaderboard import compare_boards, load_board

REPO_ROOT = Path(__file__).resolve().parent.parent
NEXT_EVENT_BOARD = REPO_ROOT / "leaderboard" / "next-event" / "synthetic-toy.json"


def test_compare_identical_boards_has_zero_deltas() -> None:
    a = load_board(NEXT_EVENT_BOARD)
    b = load_board(NEXT_EVENT_BOARD)
    result = compare_boards(a, b)
    assert result["only_in_a"] == []
    assert result["only_in_b"] == []
    for entry in result["compared"]:
        for v in entry["scores"].values():
            if "delta" in v:
                assert v["delta"] == 0


def test_compare_detects_score_change(tmp_path: Path) -> None:
    raw = json.loads(NEXT_EVENT_BOARD.read_text())
    # Bump markov-ref's top1 by 0.05 in the b copy
    b_path = tmp_path / "b.json"
    raw["entries"][0]["score"]["top1"] += 0.05
    b_path.write_text(json.dumps(raw))

    a = load_board(NEXT_EVENT_BOARD)
    b = load_board(b_path)
    result = compare_boards(a, b)

    markov_entry = next(e for e in result["compared"] if e["model"] == "markov-ref")
    assert abs(markov_entry["scores"]["top1"]["delta"] - 0.05) < 1e-9


def test_compare_surfaces_only_in_b(tmp_path: Path) -> None:
    raw = json.loads(NEXT_EVENT_BOARD.read_text())
    raw["entries"].append({
        "model": "newcomer",
        "version": "0.1.0",
        "predictions_path": "x",
        "score": {"top1": 0.5, "top3": 0.7, "n": 1},
    })
    b_path = tmp_path / "b.json"
    b_path.write_text(json.dumps(raw))

    a = load_board(NEXT_EVENT_BOARD)
    b = load_board(b_path)
    result = compare_boards(a, b)
    assert "newcomer" in result["only_in_b"]
    assert "newcomer" not in result["only_in_a"]


def test_compare_rejects_different_tasks(tmp_path: Path) -> None:
    a = load_board(NEXT_EVENT_BOARD)
    other = load_board(REPO_ROOT / "leaderboard" / "outcome" / "synthetic-toy.json")
    with pytest.raises(ValueError, match="can't compare"):
        compare_boards(a, other)


def test_cli_compare_smoke(tmp_path: Path) -> None:
    raw = json.loads(NEXT_EVENT_BOARD.read_text())
    raw["entries"][0]["score"]["top1"] += 0.01
    b_path = tmp_path / "b.json"
    b_path.write_text(json.dumps(raw))

    runner = CliRunner()
    r = runner.invoke(main, ["compare", str(NEXT_EVENT_BOARD), str(b_path)])
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["task"] == "next-event"
    assert any(
        abs(e["scores"]["top1"].get("delta", 0) - 0.01) < 1e-9
        for e in out["compared"]
        if e["model"] == "markov-ref"
    )


def test_cli_compare_different_tasks_exits_nonzero() -> None:
    runner = CliRunner()
    r = runner.invoke(
        main,
        [
            "compare",
            str(NEXT_EVENT_BOARD),
            str(REPO_ROOT / "leaderboard" / "outcome" / "synthetic-toy.json"),
        ],
    )
    assert r.exit_code == 1
    assert "can't compare" in r.output
