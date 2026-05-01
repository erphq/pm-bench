import pytest

from pm_bench import score_next_event


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
