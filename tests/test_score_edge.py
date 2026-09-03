"""Edge-case and boundary tests for pm_bench scoring functions.

Covers paths not exercised by test_score.py: all-miss top-3, exact
top-3 boundary, conformance perfect match, bottleneck k < n_transitions,
and remaining-time with n=1.
"""
from __future__ import annotations

from pm_bench import (
    score_bottleneck,
    score_conformance,
    score_next_event,
    score_remaining_time,
)

# ---- score_next_event edge cases -----------------------------------------


def test_next_event_all_miss_top3_is_zero() -> None:
    """All predictions wrong even in top-3: top3=0.0."""
    preds = [["x", "y", "z"], ["p", "q", "r"]]
    truth = ["a", "b"]
    s = score_next_event(preds, truth)
    assert s.top1 == 0.0
    assert s.top3 == 0.0
    assert s.n == 2


def test_next_event_truth_at_rank3_counts_for_top3_only() -> None:
    """Truth at exactly the 3rd rank (index 2): top3=1.0, top1=0.0."""
    preds = [["x", "y", "a"]]
    truth = ["a"]
    s = score_next_event(preds, truth)
    assert s.top1 == 0.0
    assert s.top3 == 1.0
    assert s.n == 1


def test_next_event_truth_at_rank4_misses_top3() -> None:
    """Truth at rank 4 (index 3) does not count for top-3."""
    preds = [["x", "y", "z", "a"]]
    truth = ["a"]
    s = score_next_event(preds, truth)
    assert s.top1 == 0.0
    assert s.top3 == 0.0


# ---- score_conformance edge cases ----------------------------------------


def test_conformance_perfect_match_fscore_one() -> None:
    """Model identical to test set: fitness=precision=fscore=1.0."""
    transitions = {("a", "b"), ("b", "c"), ("c", "d")}
    s = score_conformance(transitions, transitions)
    assert s.fitness == 1.0
    assert s.precision == 1.0
    assert s.fscore == 1.0
    assert s.n_test_transitions == 3
    assert s.n_model_transitions == 3


def test_conformance_single_transition_perfect() -> None:
    """Single-transition model perfectly matching a single-transition test."""
    edge = {("start", "end")}
    s = score_conformance(edge, edge)
    assert s.fscore == 1.0
    assert s.n_test_transitions == 1
    assert s.n_model_transitions == 1


# ---- score_bottleneck edge cases -----------------------------------------


def test_bottleneck_k_less_than_n_transitions_perfect() -> None:
    """k < n_transitions with perfect top-k predictions: NDCG@k = 1.0."""
    truth = {("a", "b"): 10.0, ("c", "d"): 5.0, ("e", "f"): 1.0}
    preds = {("a", "b"): 10.0, ("c", "d"): 5.0, ("e", "f"): 1.0}
    s = score_bottleneck(preds, truth, k=2)
    assert s.k == 2
    assert s.n_transitions == 3
    assert s.ndcg_at_k == 1.0


def test_bottleneck_k_one_correct_top_prediction() -> None:
    """k=1 with the correct highest-wait transition predicted first."""
    truth = {("a", "b"): 10.0, ("c", "d"): 5.0}
    preds = {("a", "b"): 100.0, ("c", "d"): 1.0}
    s = score_bottleneck(preds, truth, k=1)
    assert s.ndcg_at_k == 1.0
    assert s.k == 1


# ---- score_remaining_time edge cases -------------------------------------


def test_remaining_time_single_sample() -> None:
    """n=1 is the minimum valid input; MAE equals the absolute error."""
    s = score_remaining_time([3.0], [5.0])
    assert s.mae_days == 2.0
    assert s.n == 1


def test_remaining_time_zero_predictions_valid() -> None:
    """A model that always predicts 0 days remaining is legal; MAE = mean truth."""
    s = score_remaining_time([0.0, 0.0], [2.0, 4.0])
    assert s.mae_days == 3.0
    assert s.n == 2
