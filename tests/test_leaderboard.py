"""Leaderboard determinism + drift detection.

The Markov reference entry under leaderboard/next-event/synthetic-toy.json
is the canary: if its recorded score doesn't match what we re-compute
today, either the Markov code changed or the entry is stale. Either
way, contributors should know.
"""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from pm_bench.cli import main
from pm_bench.leaderboard import load_board, rescore, standings, verify

REPO_ROOT = Path(__file__).resolve().parent.parent
BOARD_PATH = REPO_ROOT / "leaderboard" / "next-event" / "synthetic-toy.json"


def test_synthetic_toy_board_loads() -> None:
    board = load_board(BOARD_PATH)
    assert board.task == "next-event"
    assert board.dataset == "synthetic-toy"
    assert len(board.entries) >= 1


def test_markov_ref_has_no_score_drift() -> None:
    """Recorded score must match a fresh rescore — guards model code."""
    board = load_board(BOARD_PATH)
    drifts = verify(board, repo_root=REPO_ROOT)
    assert drifts == [], drifts


def test_rescore_returns_one_pair_per_entry() -> None:
    board = load_board(BOARD_PATH)
    pairs = rescore(board, repo_root=REPO_ROOT)
    assert len(pairs) == len(board.entries)
    for _entry, fresh in pairs:
        assert "top1" in fresh and "top3" in fresh and "n" in fresh
        assert 0.0 <= fresh["top1"] <= 1.0


def test_standings_orders_by_top1_desc() -> None:
    board = load_board(BOARD_PATH)
    s = standings(board)
    scores = [e.score["top1"] for e in s]
    assert scores == sorted(scores, reverse=True)


def test_verify_detects_drift(tmp_path) -> None:
    """A tampered score must surface as a drift message."""
    src = json.loads(BOARD_PATH.read_text())
    src["entries"][0]["score"]["top1"] = 0.111
    fake = tmp_path / "fake.json"
    fake.write_text(json.dumps(src))
    # The tampered file still references the real predictions; we point
    # repo_root at the real repo so the predictions resolve.
    board = load_board(fake)
    drifts = verify(board, repo_root=REPO_ROOT)
    assert any("top1 drift" in d for d in drifts)


def test_cli_leaderboard_verify_passes() -> None:
    """`pm-bench leaderboard ... --verify` must exit 0 and report 'no drift'."""
    runner = CliRunner()
    r = runner.invoke(
        main,
        ["leaderboard", "next-event", "synthetic-toy", "--verify", "--repo-root", str(REPO_ROOT)],
    )
    assert r.exit_code == 0, r.output
    assert "no drift" in r.output


def test_cli_leaderboard_missing_returns_nonzero(tmp_path) -> None:
    """Asking for a nonexistent (task, dataset) pair must error cleanly."""
    # Lay out a partial repo with no leaderboard file.
    (tmp_path / "leaderboard" / "next-event").mkdir(parents=True)
    runner = CliRunner()
    r = runner.invoke(
        main,
        ["leaderboard", "next-event", "no-such-dataset", "--repo-root", str(tmp_path)],
    )
    assert r.exit_code == 1
    assert "no leaderboard at" in r.output


def test_predictions_file_is_readable_gz() -> None:
    """The reference predictions must be a real gzip — not a placeholder."""
    p = (
        REPO_ROOT
        / "leaderboard"
        / "predictions"
        / "next-event"
        / "synthetic-toy"
        / "markov-ref.csv.gz"
    )
    assert p.exists()
    # First two bytes of a gzip file are 0x1f 0x8b.
    head = p.read_bytes()[:2]
    assert head == b"\x1f\x8b"


