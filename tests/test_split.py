import datetime as dt

import pytest

from pm_bench import _synth, case_chrono_split


def test_synthetic_split_sizes() -> None:
    events = list(_synth.synthetic_log(n_cases=100, seed=42))
    s = case_chrono_split(events)
    assert len(s.train) == 70
    assert len(s.val) == 10
    assert len(s.test) == 20
    assert set(s.train).isdisjoint(s.val)
    assert set(s.train).isdisjoint(s.test)
    assert set(s.val).isdisjoint(s.test)


def test_split_orders_by_first_event_timestamp() -> None:
    base = dt.datetime(2024, 1, 1)
    events: list = []
    for i in range(10):
        events.append((str(i), "a", base + dt.timedelta(days=i)))
    s = case_chrono_split(events, train_frac=0.7, val_frac=0.1)
    assert s.train == ["0", "1", "2", "3", "4", "5", "6"]
    assert s.val == ["7"]
    assert s.test == ["8", "9"]


def test_split_handles_empty() -> None:
    s = case_chrono_split([])
    assert s.sizes() == (0, 0, 0)


def test_split_is_deterministic_under_same_start_timestamps() -> None:
    """When N cases share an identical start time, the partition order
    must depend only on case_id (deterministic) — not on the order of
    events in the input list (non-deterministic across producers)."""
    base = dt.datetime(2024, 1, 1)
    forward = [(str(i), "a", base) for i in range(20)]
    reversed_input = list(reversed(forward))
    s_forward = case_chrono_split(forward, train_frac=0.7, val_frac=0.1)
    s_reversed = case_chrono_split(reversed_input, train_frac=0.7, val_frac=0.1)
    assert s_forward.train == s_reversed.train
    assert s_forward.val == s_reversed.val
    assert s_forward.test == s_reversed.test


def test_split_validates_fracs() -> None:
    with pytest.raises(ValueError):
        case_chrono_split([], train_frac=0.99, val_frac=0.5)
    with pytest.raises(ValueError):
        case_chrono_split([], train_frac=1.5, val_frac=0.1)
    with pytest.raises(ValueError):
        case_chrono_split([], train_frac=0.7, val_frac=-0.1)
