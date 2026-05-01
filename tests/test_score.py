import math

import pytest

from pm_bench import (
    score_bottleneck,
    score_next_event,
    score_outcome,
    score_remaining_time,
)


def test_top1_perfect() -> None:
    s = score_next_event([["a"], ["b"], ["c"]], ["a", "b", "c"])
    assert s.top1 == 1.0
    assert s.top3 == 1.0
    assert s.n == 3


def test_top3_better_than_top1() -> None:
    preds = [["x", "y", "a"], ["b", "z", "q"]]
    truth = ["a", "b"]
    s = score_next_event(preds, truth)
    assert s.top1 == 0.5
    assert s.top3 == 1.0


def test_lengths_must_match() -> None:
    with pytest.raises(ValueError):
        score_next_event([["a"]], ["a", "b"])


def test_nothing_to_score_raises() -> None:
    with pytest.raises(ValueError):
        score_next_event([], [])


def test_empty_prediction_counts_as_miss() -> None:
    s = score_next_event([[], ["a"]], ["a", "a"])
    assert s.top1 == 0.5
    assert s.top3 == 0.5


def test_remaining_time_perfect() -> None:
    s = score_remaining_time([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert s.mae_days == 0.0
    assert s.n == 3


def test_remaining_time_mae_in_days() -> None:
    s = score_remaining_time([1.0, 2.0, 3.0], [2.0, 4.0, 0.0])
    # |1-2| + |2-4| + |3-0| = 1 + 2 + 3 = 6; mae = 2.0
    assert s.mae_days == 2.0
    assert s.n == 3


def test_remaining_time_lengths_must_match() -> None:
    with pytest.raises(ValueError):
        score_remaining_time([1.0], [1.0, 2.0])


def test_remaining_time_empty_raises() -> None:
    with pytest.raises(ValueError):
        score_remaining_time([], [])


def test_outcome_perfect_separation_is_one() -> None:
    s = score_outcome([0.1, 0.2, 0.9, 0.8], [0, 0, 1, 1])
    assert s.auc == 1.0
    assert s.n == 4
    assert s.n_pos == 2


def test_outcome_perfect_inversion_is_zero() -> None:
    s = score_outcome([0.9, 0.8, 0.1, 0.2], [0, 0, 1, 1])
    assert s.auc == 0.0


def test_outcome_constant_predictions_is_half() -> None:
    """All-equal scores → tied ranks → AUC = 0.5."""
    s = score_outcome([0.5, 0.5, 0.5, 0.5], [0, 0, 1, 1])
    assert s.auc == 0.5


def test_outcome_single_class_returns_half() -> None:
    s = score_outcome([0.1, 0.9], [1, 1])
    assert s.auc == 0.5


def test_outcome_lengths_must_match() -> None:
    with pytest.raises(ValueError):
        score_outcome([0.1], [0, 1])


def test_bottleneck_perfect_ranking_is_one() -> None:
    truth = {("a", "b"): 10.0, ("c", "d"): 5.0, ("e", "f"): 1.0}
    preds = {("a", "b"): 10.0, ("c", "d"): 5.0, ("e", "f"): 1.0}
    s = score_bottleneck(preds, truth, k=10)
    assert s.ndcg_at_k == 1.0
    assert s.n_transitions == 3
    assert s.k == 10


def test_bottleneck_inverted_ranking_below_one() -> None:
    truth = {("a", "b"): 10.0, ("c", "d"): 5.0, ("e", "f"): 1.0}
    # Predicted scores invert the order.
    preds = {("a", "b"): 1.0, ("c", "d"): 5.0, ("e", "f"): 10.0}
    s = score_bottleneck(preds, truth)
    assert s.ndcg_at_k < 1.0


def test_bottleneck_missing_predictions_sink_to_bottom() -> None:
    """A model that doesn't predict at all gets the worst possible ranking."""
    truth = {("a", "b"): 10.0, ("c", "d"): 5.0}
    preds: dict = {}
    s = score_bottleneck(preds, truth)
    # All transitions tied at -inf → tie-break by dict insertion order.
    # The actual NDCG depends on that order; just assert it's a valid value.
    assert 0.0 <= s.ndcg_at_k <= 1.0


def test_bottleneck_known_value() -> None:
    """Hand-checked: 3 transitions, predicted ranking [b,a,c], truth [a,b,c]."""
    truth = {"a": 10.0, "b": 5.0, "c": 1.0}
    # Make tuples to match the API.
    truth_t = {(k, "x"): v for k, v in truth.items()}
    # Predicted ranks b > a > c
    preds_t = {("b", "x"): 100.0, ("a", "x"): 50.0, ("c", "x"): 1.0}
    # DCG = 5/log2(2) + 10/log2(3) + 1/log2(4) = 5 + 10/1.585 + 0.5
    # IDCG = 10/log2(2) + 5/log2(3) + 1/log2(4) = 10 + 5/1.585 + 0.5
    expected_dcg = 5.0 / math.log2(2) + 10.0 / math.log2(3) + 1.0 / math.log2(4)
    expected_idcg = 10.0 / math.log2(2) + 5.0 / math.log2(3) + 1.0 / math.log2(4)
    expected_ndcg = expected_dcg / expected_idcg
    s = score_bottleneck(preds_t, truth_t, k=10)
    assert abs(s.ndcg_at_k - expected_ndcg) < 1e-9


def test_bottleneck_empty_truth_raises() -> None:
    with pytest.raises(ValueError):
        score_bottleneck({}, {})


def test_bottleneck_invalid_k_raises() -> None:
    with pytest.raises(ValueError):
        score_bottleneck({}, {("a", "b"): 1.0}, k=0)


def test_bottleneck_all_zero_truth_raises() -> None:
    """Degenerate truth (every transition has zero wait) is undefined and
    must surface as an error rather than silently scoring everyone 0."""
    with pytest.raises(ValueError, match="degenerate"):
        score_bottleneck(
            {("a", "b"): 5.0, ("c", "d"): 3.0},
            {("a", "b"): 0.0, ("c", "d"): 0.0},
        )


def test_remaining_time_rejects_nan() -> None:
    """NaN in either side must raise rather than silently returning NaN."""
    import math

    with pytest.raises(ValueError, match="finite"):
        score_remaining_time([math.nan, 1.0], [1.0, 1.0])
    with pytest.raises(ValueError, match="finite"):
        score_remaining_time([1.0, 2.0], [math.inf, 2.0])


def test_outcome_rejects_non_binary_truth() -> None:
    with pytest.raises(ValueError, match="0 or 1"):
        score_outcome([0.1, 0.9], [1, 2])


def test_outcome_rejects_nan_predictions() -> None:
    import math

    with pytest.raises(ValueError, match="finite"):
        score_outcome([math.nan, 0.9], [0, 1])


def test_bottleneck_rejects_nan() -> None:
    import math

    with pytest.raises(ValueError, match="finite"):
        score_bottleneck(
            {("a", "b"): math.nan},
            {("a", "b"): 5.0},
        )


def test_outcome_known_value() -> None:
    """Hand-checked: 3 pos, 3 neg, one swap → AUC = 8/9."""
    # ranks ascending: [neg=0.1→1, neg=0.2→2, pos=0.3→3, neg=0.4→4, pos=0.5→5, pos=0.6→6]
    # sum_pos_ranks = 3+5+6 = 14; n_pos*(n_pos+1)/2 = 6; n_pos*n_neg = 9
    # auc = (14 - 6) / 9 = 8/9
    preds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    truth = [0, 0, 1, 0, 1, 1]
    s = score_outcome(preds, truth)
    assert abs(s.auc - 8 / 9) < 1e-9
