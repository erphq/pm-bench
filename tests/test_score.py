import pytest

from pm_bench import score_next_event, score_remaining_time


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
