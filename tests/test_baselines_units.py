"""Unit-test contracts for the secondary-baseline functions.

These were previously only exercised indirectly via leaderboard rescore,
which is too coarse — a leaderboard-drift CI failure on a baseline
regression would be hard to root-cause. These tests pin the documented
behavior of each baseline.
"""
from __future__ import annotations

import datetime as dt

from pm_bench import Prefix
from pm_bench.baselines.global_rate import fit_global_rate, predict_global_rate
from pm_bench.baselines.random_rank import predict_random_rank
from pm_bench.baselines.uniform import fit_uniform, predict_uniform
from pm_bench.baselines.zero_time import predict_zero_time
from pm_bench.bottleneck import BottleneckTarget
from pm_bench.prefixes import OutcomeTarget, TimeTarget


def _events() -> list[tuple[str, str, dt.datetime]]:
    base = dt.datetime(2024, 1, 1)
    return [
        ("c1", "a", base),
        ("c1", "b", base + dt.timedelta(hours=1)),
        ("c1", "c", base + dt.timedelta(hours=2)),
        ("c2", "a", base),
        ("c2", "b", base + dt.timedelta(hours=1)),
        ("c2", "x", base + dt.timedelta(hours=2)),
    ]


def test_uniform_collects_training_activities() -> None:
    model = fit_uniform(_events(), ["c1"])
    # c1 has activities {a, b, c}
    assert model.activities_sorted == ("a", "b", "c")


def test_uniform_excludes_test_only_activities() -> None:
    """Activities seen only in test cases must not leak into the ranking."""
    model = fit_uniform(_events(), ["c1"])  # train = c1
    # 'x' is only in c2 (test); must not appear
    assert "x" not in model.activities_sorted


def test_uniform_emits_same_ranking_for_every_target() -> None:
    model = fit_uniform(_events(), ["c1"])
    targets = [
        Prefix(case_id="cx", prefix_idx=1, prefix=("a",), true_next="?"),
        Prefix(case_id="cy", prefix_idx=2, prefix=("a", "b"), true_next="?"),
    ]
    preds = predict_uniform(model, targets)
    # All predictions identical and equal to the sorted training vocabulary
    assert preds[0].ranked == model.activities_sorted
    assert preds[1].ranked == model.activities_sorted


def test_zero_time_returns_zero_for_every_target() -> None:
    targets = [
        TimeTarget(case_id="c1", prefix_idx=1, remaining_days=5.0),
        TimeTarget(case_id="c1", prefix_idx=2, remaining_days=2.0),
    ]
    preds = predict_zero_time(targets)
    assert all(p.predicted_days == 0.0 for p in preds)
    assert len(preds) == 2


def _is_pay(activities: list[str]) -> bool:
    return bool(activities) and activities[-1] == "pay"


def test_global_rate_uses_per_case_count() -> None:
    """The rate is fraction of cases meeting the rule, not fraction of prefixes."""
    base = dt.datetime(2024, 1, 1)
    events = []
    # 1 positive case (ends with pay), 3 negative (end with cancel)
    for cid, last in [("c1", "pay"), ("c2", "cancel"), ("c3", "cancel"), ("c4", "cancel")]:
        events.append((cid, "start", base))
        events.append((cid, last, base + dt.timedelta(hours=1)))
    model = fit_global_rate(events, ["c1", "c2", "c3", "c4"], _is_pay)
    assert model.positive_rate == 0.25  # 1 of 4 cases positive


def test_global_rate_predicts_constant() -> None:
    base = dt.datetime(2024, 1, 1)
    events = [
        ("c1", "start", base),
        ("c1", "pay", base + dt.timedelta(hours=1)),
    ]
    model = fit_global_rate(events, ["c1"], _is_pay)
    targets = [
        OutcomeTarget(case_id="any", prefix_idx=1, outcome=0),
        OutcomeTarget(case_id="other", prefix_idx=5, outcome=1),
    ]
    preds = predict_global_rate(model, targets)
    assert preds[0].score == preds[1].score == model.positive_rate


def test_random_rank_is_deterministic() -> None:
    """Same (a, b) pair must hash to the same score on every invocation
    so checked-in leaderboard predictions don't drift across CI runs."""
    targets = [BottleneckTarget("a", "b", 1.0, 1)]
    p1 = predict_random_rank(targets)
    p2 = predict_random_rank(targets)
    assert p1[0].predicted_wait_seconds == p2[0].predicted_wait_seconds


def test_random_rank_score_in_unit_interval() -> None:
    """Score is derived from sha256 / 2^64 → must lie in [0, 1)."""
    targets = [
        BottleneckTarget("a", "b", 1.0, 1),
        BottleneckTarget("c", "d", 1.0, 1),
        BottleneckTarget("e", "f", 1.0, 1),
    ]
    preds = predict_random_rank(targets)
    for p in preds:
        assert 0.0 <= p.predicted_wait_seconds < 1.0


def test_random_rank_distinct_pairs_get_distinct_scores() -> None:
    """sha256 collisions on 8 bytes are vanishingly rare; assert no
    accidental ties on a small set of distinct transitions."""
    targets = [
        BottleneckTarget("a", "b", 1.0, 1),
        BottleneckTarget("c", "d", 1.0, 1),
        BottleneckTarget("e", "f", 1.0, 1),
    ]
    preds = predict_random_rank(targets)
    scores = [p.predicted_wait_seconds for p in preds]
    assert len(set(scores)) == len(scores)
