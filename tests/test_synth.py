from pm_bench import _synth
from pm_bench._synth import is_positive_outcome


def test_is_positive_outcome_true_when_ends_with_delivery_confirmed() -> None:
    assert is_positive_outcome(["received", "ship_order", "delivery_confirmed"])


def test_is_positive_outcome_false_when_ends_with_other_activity() -> None:
    assert not is_positive_outcome(["received", "ship_order"])


def test_is_positive_outcome_false_on_empty_list() -> None:
    assert not is_positive_outcome([])


def test_is_positive_outcome_false_when_delivery_confirmed_not_last() -> None:
    assert not is_positive_outcome(["delivery_confirmed", "received"])


def test_is_positive_outcome_true_on_single_event_delivery_confirmed() -> None:
    assert is_positive_outcome(["delivery_confirmed"])


def test_synthetic_log_positive_rate_matches_paths_weight() -> None:
    """PATHS[4] has weight 0.10; rate on a large sample should be close."""
    events = list(_synth.synthetic_log(n_cases=500, seed=42))
    by_case: dict[str, list[str]] = {}
    for cid, act, _ in events:
        by_case.setdefault(cid, []).append(act)
    positives = sum(1 for acts in by_case.values() if is_positive_outcome(acts))
    rate = positives / len(by_case)
    assert 0.05 <= rate <= 0.20, f"positive rate {rate:.3f} outside expected range"


def test_deterministic() -> None:
    a = list(_synth.synthetic_log(n_cases=20, seed=42))
    b = list(_synth.synthetic_log(n_cases=20, seed=42))
    assert a == b


def test_different_seeds_diverge() -> None:
    a = list(_synth.synthetic_log(n_cases=20, seed=1))
    b = list(_synth.synthetic_log(n_cases=20, seed=2))
    assert a != b


def test_event_count_reasonable() -> None:
    events = list(_synth.synthetic_log(n_cases=50, seed=42))
    assert len(events) >= 100
    case_ids = {c for c, _, _ in events}
    assert len(case_ids) == 50


def test_timestamps_monotonic_within_case() -> None:
    events = list(_synth.synthetic_log(n_cases=20, seed=42))
    by_case: dict[str, list] = {}
    for cid, _, ts in events:
        by_case.setdefault(cid, []).append(ts)
    for ts_list in by_case.values():
        assert ts_list == sorted(ts_list)
