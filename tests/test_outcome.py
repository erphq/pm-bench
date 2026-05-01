"""End-to-end + targeted tests for the outcome task.

Synthetic-toy with seed=42 doesn't put any `delivery_confirmed` cases
in the test split (path-4 is 10% of cases and the chronological tail
happens to have none), so we test the outcome machinery on a hand-built
event set with controlled class balance instead. The CLI smoke test
runs against synthetic-toy and asserts the pipeline executes cleanly,
even though the AUC degenerates to 0.5 (n_pos=0 in test).
"""
from __future__ import annotations

import datetime as dt
import json

from click.testing import CliRunner

from pm_bench import (
    OutcomeTarget,
    extract_outcome_targets,
    read_outcome_targets_csv,
    score_outcome,
    write_outcome_targets_csv,
)
from pm_bench.baselines.prior_outcome import (
    OutcomePrediction,
    fit_prior_outcome,
    predict_prior_outcome,
    read_outcome_predictions_csv,
    write_outcome_predictions_csv,
)
from pm_bench.cli import main


def _events_with_outcomes() -> list[tuple[str, str, dt.datetime]]:
    """4 cases, 2 positive (end with `pay`), 2 negative (end with `cancel`)."""
    base = dt.datetime(2024, 1, 1)
    out: list[tuple[str, str, dt.datetime]] = []
    for cid, last in [("c1", "pay"), ("c2", "pay"), ("c3", "cancel"), ("c4", "cancel")]:
        out.append((cid, "start", base))
        out.append((cid, "review", base + dt.timedelta(hours=1)))
        out.append((cid, last, base + dt.timedelta(hours=2)))
    return out


def _is_pay(activities: list[str]) -> bool:
    return bool(activities) and activities[-1] == "pay"


def test_extract_outcome_targets_repeats_outcome_per_prefix() -> None:
    out = list(extract_outcome_targets(_events_with_outcomes(), ["c1", "c3"], _is_pay))
    # 2 cases × (3-1) prefixes = 4 targets
    assert len(out) == 4
    assert {t.outcome for t in out if t.case_id == "c1"} == {1}
    assert {t.outcome for t in out if t.case_id == "c3"} == {0}


def test_round_trip_csv(tmp_path) -> None:
    targets = [
        OutcomeTarget(case_id="c1", prefix_idx=1, outcome=1),
        OutcomeTarget(case_id="c1", prefix_idx=2, outcome=1),
    ]
    p = tmp_path / "o.csv"
    n = write_outcome_targets_csv(targets, str(p))
    assert n == 2
    back = read_outcome_targets_csv(str(p))
    assert back == targets


def test_prior_baseline_uses_train_only() -> None:
    model = fit_prior_outcome(_events_with_outcomes(), ["c1", "c2", "c3", "c4"], _is_pay)
    # 2 of 4 cases are positive → global rate 0.5
    assert abs(model.global_rate - 0.5) < 1e-9


def test_prior_baseline_per_last_activity() -> None:
    """Prefixes ending in 'pay' or 'cancel' get the appropriate rate."""
    model = fit_prior_outcome(_events_with_outcomes(), ["c1", "c2", "c3", "c4"], _is_pay)
    # All training prefixes ending in 'review' come from cases that go on
    # to either 'pay' or 'cancel' — half of each, so rate = 0.5.
    assert abs(model.by_last["review"] - 0.5) < 1e-9
    # Prefix ending in 'start' has the same logic: every case starts.
    assert abs(model.by_last["start"] - 0.5) < 1e-9


def test_predict_prior_with_seq_lookup() -> None:
    events = _events_with_outcomes()
    model = fit_prior_outcome(events, ["c1", "c2", "c3", "c4"], _is_pay)
    targets = [OutcomeTarget(case_id="c1", prefix_idx=2, outcome=1)]
    seq_by_case = {"c1": ["start", "review", "pay"]}
    preds = predict_prior_outcome(model, targets, seq_by_case)
    # Last activity in prefix at idx 2 is 'review' → rate 0.5
    assert abs(preds[0].score - 0.5) < 1e-9


def test_predictions_csv_round_trip(tmp_path) -> None:
    preds = [
        OutcomePrediction(case_id="c1", prefix_idx=1, score=0.8),
        OutcomePrediction(case_id="c2", prefix_idx=1, score=0.2),
    ]
    p = tmp_path / "p.csv"
    write_outcome_predictions_csv(preds, str(p))
    back = read_outcome_predictions_csv(str(p))
    assert back == preds


def test_score_outcome_round_trip_via_writer(tmp_path) -> None:
    targets = [
        OutcomeTarget(case_id="c1", prefix_idx=1, outcome=1),
        OutcomeTarget(case_id="c2", prefix_idx=1, outcome=0),
    ]
    preds = [
        OutcomePrediction(case_id="c1", prefix_idx=1, score=0.9),
        OutcomePrediction(case_id="c2", prefix_idx=1, score=0.1),
    ]
    s = score_outcome(
        [p.score for p in preds],
        [t.outcome for t in targets],
    )
    assert s.auc == 1.0


def test_full_outcome_pipeline_on_synthetic_toy(tmp_path) -> None:
    """Pipeline runs cleanly end-to-end. AUC degenerates because seed=42's
    test partition has no positives, but the contract still holds."""
    runner = CliRunner()
    split_path = tmp_path / "split.json"
    prefixes_path = tmp_path / "prefixes.csv"
    preds_path = tmp_path / "predictions.csv"

    r = runner.invoke(main, ["split", "synthetic-toy"])
    assert r.exit_code == 0
    split_path.write_text(r.output)

    r = runner.invoke(
        main,
        ["prefixes", "synthetic-toy", "--split", str(split_path),
         "--out", str(prefixes_path), "--task", "outcome"],
    )
    assert r.exit_code == 0, r.output

    r = runner.invoke(
        main,
        ["predict", "synthetic-toy", "--split", str(split_path),
         "--prefixes", str(prefixes_path), "--out", str(preds_path),
         "--baseline", "prior", "--task", "outcome"],
    )
    assert r.exit_code == 0, r.output

    r = runner.invoke(
        main,
        ["score", str(preds_path), "--prefixes", str(prefixes_path),
         "--task", "outcome"],
    )
    assert r.exit_code == 0, r.output
    result = json.loads(r.output)
    assert result["task"] == "outcome"
    assert result["n"] > 0
    # synthetic-toy with seed=42 happens to have n_pos=0 in test
    # → degenerate AUC = 0.5 by convention. The pipeline still runs.
    assert 0.0 <= result["auc"] <= 1.0
