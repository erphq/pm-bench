import pytest

from pm_bench import score_next_event, score_outcome, score_remaining_time


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


def test_outcome_known_value() -> None:
    """Hand-checked: 3 pos, 3 neg, one swap → AUC = 8/9."""
    # ranks ascending: [neg=0.1→1, neg=0.2→2, pos=0.3→3, neg=0.4→4, pos=0.5→5, pos=0.6→6]
    # sum_pos_ranks = 3+5+6 = 14; n_pos*(n_pos+1)/2 = 6; n_pos*n_neg = 9
    # auc = (14 - 6) / 9 = 8/9
    preds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    truth = [0, 0, 1, 0, 1, 1]
    s = score_outcome(preds, truth)
    assert abs(s.auc - 8 / 9) < 1e-9
