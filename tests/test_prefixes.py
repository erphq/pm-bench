import datetime as dt

from pm_bench import (
    Prefix,
    extract_prefixes,
    read_prefixes_csv,
    write_prefixes_csv,
)


def _events() -> list[tuple[str, str, dt.datetime]]:
    base = dt.datetime(2024, 1, 1)
    return [
        ("c1", "a", base),
        ("c1", "b", base + dt.timedelta(hours=1)),
        ("c1", "c", base + dt.timedelta(hours=2)),
        ("c2", "x", base),
        ("c2", "y", base + dt.timedelta(hours=1)),
        ("c3", "solo", base),  # length-1 case, gets skipped
    ]


def test_extract_prefixes_yields_n_minus_1_per_case() -> None:
    out = list(extract_prefixes(_events(), ["c1", "c2", "c3"]))
    # c1 → 2 targets, c2 → 1 target, c3 (len 1) → 0
    assert len(out) == 3


def test_extract_prefixes_respects_chronology() -> None:
    base = dt.datetime(2024, 1, 1)
    shuffled = [
        ("c1", "c", base + dt.timedelta(hours=2)),
        ("c1", "a", base),
        ("c1", "b", base + dt.timedelta(hours=1)),
    ]
    out = list(extract_prefixes(shuffled, ["c1"]))
    assert out[0].prefix == ("a",)
    assert out[0].true_next == "b"
    assert out[1].prefix == ("a", "b")
    assert out[1].true_next == "c"


def test_extract_prefixes_filters_to_kept_cases() -> None:
    out = list(extract_prefixes(_events(), ["c1"]))
    assert {p.case_id for p in out} == {"c1"}


def test_round_trip_csv(tmp_path) -> None:
    prefixes = [
        Prefix(case_id="c1", prefix_idx=1, prefix=("a",), true_next="b"),
        Prefix(case_id="c1", prefix_idx=2, prefix=("a", "b"), true_next="c"),
    ]
    path = tmp_path / "prefixes.csv"
    n = write_prefixes_csv(prefixes, str(path))
    assert n == 2
    back = read_prefixes_csv(str(path))
    assert back == prefixes


def test_write_prefixes_csv_rejects_pipe_in_activity(tmp_path) -> None:
    """The `|` separator must not appear in any activity name —
    silently corrupting the round-trip is the worst outcome."""
    import pytest as _pytest

    bad = [Prefix(case_id="c1", prefix_idx=1, prefix=("a|b",), true_next="c")]
    with _pytest.raises(ValueError, match="separator"):
        write_prefixes_csv(bad, str(tmp_path / "x.csv"))


def test_write_prefixes_csv_rejects_empty_activity(tmp_path) -> None:
    """Empty-string activity is the encoding's 'no activities' sentinel
    on read — writing it would silently lose the activity."""
    import pytest as _pytest

    bad = [Prefix(case_id="c1", prefix_idx=1, prefix=("",), true_next="c")]
    with _pytest.raises(ValueError, match="empty string"):
        write_prefixes_csv(bad, str(tmp_path / "x.csv"))


def test_extract_prefixes_rejects_mixed_type_case_ids() -> None:
    """Mixed int/str case_ids would break sorted iteration; surface clearly."""
    import pytest as _pytest

    base = dt.datetime(2024, 1, 1)
    events = [(1, "a", base), ("c2", "b", base)]
    with _pytest.raises(TypeError, match="same type"):
        list(extract_prefixes(events, [1, "c2"]))
