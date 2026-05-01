from pm_bench import _synth


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
