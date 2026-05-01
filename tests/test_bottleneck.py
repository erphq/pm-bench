"""End-to-end + targeted tests for the bottleneck task."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from click.testing import CliRunner

from pm_bench.baselines.mean_wait import fit_mean_wait, predict_mean_wait
from pm_bench.bottleneck import (
    BottleneckPrediction,
    BottleneckTarget,
    extract_bottleneck_targets,
    read_bottleneck_predictions_csv,
    read_bottleneck_targets_csv,
    write_bottleneck_predictions_csv,
    write_bottleneck_targets_csv,
)
from pm_bench.cli import main
from pm_bench.leaderboard import load_board, verify

REPO_ROOT = Path(__file__).resolve().parent.parent
BOTTLENECK_BOARD = REPO_ROOT / "leaderboard" / "bottleneck" / "synthetic-toy.json"


def _events() -> list[tuple[str, str, dt.datetime]]:
    base = dt.datetime(2024, 1, 1)
    return [
        ("c1", "a", base),
        ("c1", "b", base + dt.timedelta(seconds=100)),
        ("c1", "c", base + dt.timedelta(seconds=300)),
        ("c2", "a", base),
        ("c2", "b", base + dt.timedelta(seconds=200)),
        ("c2", "c", base + dt.timedelta(seconds=500)),
    ]


def test_extract_targets_aggregates_per_transition() -> None:
    out = list(extract_bottleneck_targets(_events(), ["c1", "c2"]))
    by_pair = {(t.activity_a, t.activity_b): t for t in out}
    # a→b: 100 and 200 → mean 150; b→c: 200 and 300 → mean 250
    assert by_pair[("a", "b")].mean_wait_seconds == 150.0
    assert by_pair[("a", "b")].n_observations == 2
    assert by_pair[("b", "c")].mean_wait_seconds == 250.0


def test_round_trip_csv(tmp_path) -> None:
    targets = [
        BottleneckTarget("a", "b", 150.0, 2),
        BottleneckTarget("b", "c", 250.0, 2),
    ]
    p = tmp_path / "t.csv"
    n = write_bottleneck_targets_csv(targets, str(p))
    assert n == 2
    back = read_bottleneck_targets_csv(str(p))
    assert back == targets


def test_predictions_csv_round_trip(tmp_path) -> None:
    preds = [
        BottleneckPrediction("a", "b", 150.0),
        BottleneckPrediction("b", "c", 250.0),
    ]
    p = tmp_path / "p.csv"
    write_bottleneck_predictions_csv(preds, str(p))
    back = read_bottleneck_predictions_csv(str(p))
    assert back == preds


def test_mean_wait_baseline_matches_train_mean() -> None:
    model = fit_mean_wait(_events(), ["c1", "c2"])
    assert model.by_transition[("a", "b")] == 150.0
    assert model.by_transition[("b", "c")] == 250.0


def test_mean_wait_unseen_transition_falls_back_to_global() -> None:
    model = fit_mean_wait(_events(), ["c1", "c2"])
    targets = [BottleneckTarget("z", "y", 9999.0, 1)]
    preds = predict_mean_wait(model, targets)
    # Unseen → global mean = (150*2 + 250*2) / 4 = 200
    assert abs(preds[0].predicted_wait_seconds - 200.0) < 1e-9


def test_bottleneck_board_verifies() -> None:
    board = load_board(BOTTLENECK_BOARD)
    drifts = verify(board, repo_root=REPO_ROOT)
    assert drifts == [], drifts


def test_full_bottleneck_pipeline(tmp_path) -> None:
    runner = CliRunner()
    split_path = tmp_path / "split.json"
    targets_path = tmp_path / "targets.csv"
    preds_path = tmp_path / "preds.csv"

    r = runner.invoke(main, ["split", "synthetic-toy"])
    assert r.exit_code == 0
    split_path.write_text(r.output)

    r = runner.invoke(
        main,
        ["prefixes", "synthetic-toy", "--split", str(split_path),
         "--out", str(targets_path), "--task", "bottleneck"],
    )
    assert r.exit_code == 0, r.output

    r = runner.invoke(
        main,
        ["predict", "synthetic-toy", "--split", str(split_path),
         "--prefixes", str(targets_path), "--out", str(preds_path),
         "--baseline", "mean-wait", "--task", "bottleneck"],
    )
    assert r.exit_code == 0, r.output

    r = runner.invoke(
        main,
        ["score", str(preds_path), "--prefixes", str(targets_path),
         "--task", "bottleneck"],
    )
    assert r.exit_code == 0, r.output
    result = json.loads(r.output)
    assert result["task"] == "bottleneck"
    assert result["k"] == 10
    assert 0.0 <= result["ndcg_at_k"] <= 1.0
    # The mean-wait baseline should beat 0.5 on synthetic-toy.
    assert result["ndcg_at_k"] > 0.5
