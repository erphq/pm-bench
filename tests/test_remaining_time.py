"""End-to-end + targeted tests for the remaining-time task."""
from __future__ import annotations

import datetime as dt
import json

from click.testing import CliRunner

from pm_bench import (
    TimeTarget,
    extract_remaining_time_targets,
    read_time_targets_csv,
    write_time_targets_csv,
)
from pm_bench.baselines.mean_time import (
    fit_mean_time,
    predict_mean_time,
    read_time_predictions_csv,
    write_time_predictions_csv,
)
from pm_bench.cli import main


def _events() -> list[tuple[str, str, dt.datetime]]:
    base = dt.datetime(2024, 1, 1)
    return [
        ("c1", "a", base),
        ("c1", "b", base + dt.timedelta(days=1)),
        ("c1", "c", base + dt.timedelta(days=3)),
        ("c2", "a", base),
        ("c2", "b", base + dt.timedelta(days=2)),
        ("c2", "c", base + dt.timedelta(days=4)),
    ]


def test_extract_targets_yields_n_minus_1_per_case() -> None:
    out = list(extract_remaining_time_targets(_events(), ["c1", "c2"]))
    assert len(out) == 4  # 2 cases × 2 prefixes each


def test_remaining_days_is_nonnegative_and_decreasing_within_case() -> None:
    out = list(extract_remaining_time_targets(_events(), ["c1"]))
    # c1 ends 3 days after start; prefix at idx 1 (=after "a") has 3 days
    # remaining; idx 2 (=after "b") has 2 days remaining.
    assert out[0].remaining_days == 3.0
    assert out[1].remaining_days == 2.0


def test_round_trip_csv(tmp_path) -> None:
    targets = [
        TimeTarget(case_id="c1", prefix_idx=1, remaining_days=3.0),
        TimeTarget(case_id="c1", prefix_idx=2, remaining_days=2.0),
    ]
    p = tmp_path / "t.csv"
    n = write_time_targets_csv(targets, str(p))
    assert n == 2
    back = read_time_targets_csv(str(p))
    assert back == targets


def test_mean_baseline_uses_train_only() -> None:
    model = fit_mean_time(_events(), train_case_ids=["c1"])
    # c1 prefixes have remainings (3, 2); mean = 2.5.
    assert abs(model.mean_remaining_days - 2.5) < 1e-9


def test_predict_mean_time_emits_constant() -> None:
    model = fit_mean_time(_events(), train_case_ids=["c1", "c2"])
    targets = [
        TimeTarget(case_id="cX", prefix_idx=1, remaining_days=99.0),
        TimeTarget(case_id="cX", prefix_idx=2, remaining_days=99.0),
    ]
    preds = predict_mean_time(model, targets)
    assert preds[0].predicted_days == preds[1].predicted_days


def test_predictions_csv_round_trip(tmp_path) -> None:
    from pm_bench.baselines.mean_time import TimePrediction

    preds = [
        TimePrediction(case_id="c1", prefix_idx=1, predicted_days=2.5),
        TimePrediction(case_id="c1", prefix_idx=2, predicted_days=2.5),
    ]
    p = tmp_path / "p.csv"
    write_time_predictions_csv(preds, str(p))
    back = read_time_predictions_csv(str(p))
    assert back == preds


def test_full_remaining_time_pipeline(tmp_path) -> None:
    """split → prefixes → predict → score on synthetic-toy."""
    runner = CliRunner()
    split_path = tmp_path / "split.json"
    prefixes_path = tmp_path / "prefixes.csv"
    preds_path = tmp_path / "predictions.csv"

    r = runner.invoke(main, ["split", "synthetic-toy"])
    assert r.exit_code == 0
    split_path.write_text(r.output)

    r = runner.invoke(
        main,
        [
            "prefixes",
            "synthetic-toy",
            "--split",
            str(split_path),
            "--out",
            str(prefixes_path),
            "--task",
            "remaining-time",
        ],
    )
    assert r.exit_code == 0, r.output

    r = runner.invoke(
        main,
        [
            "predict",
            "synthetic-toy",
            "--split",
            str(split_path),
            "--prefixes",
            str(prefixes_path),
            "--out",
            str(preds_path),
            "--baseline",
            "mean",
            "--task",
            "remaining-time",
        ],
    )
    assert r.exit_code == 0, r.output

    r = runner.invoke(
        main,
        [
            "score",
            str(preds_path),
            "--prefixes",
            str(prefixes_path),
            "--task",
            "remaining-time",
        ],
    )
    assert r.exit_code == 0, r.output
    result = json.loads(r.output)
    assert result["task"] == "remaining-time"
    assert result["n"] > 0
    assert result["mae_days"] > 0  # mean baseline isn't perfect
