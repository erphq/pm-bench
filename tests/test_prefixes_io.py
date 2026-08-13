"""Round-trip and validation tests for the target CSV writers/readers.

Covers three gaps left by tests/test_prefixes.py:

1. extract_remaining_time_targets: missing mixed-type case-id rejection test.
   (extract_prefixes and extract_outcome_targets already have this guard test;
   this test fills the symmetry gap.)

2. write_time_targets_csv / read_time_targets_csv: no round-trip test existed.

3. write_outcome_targets_csv / read_outcome_targets_csv: no round-trip test existed.
"""
from __future__ import annotations

import datetime as dt

import pytest

from pm_bench import (
    OutcomeTarget,
    TimeTarget,
    extract_remaining_time_targets,
    read_outcome_targets_csv,
    read_time_targets_csv,
    write_outcome_targets_csv,
    write_time_targets_csv,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts(offset_hours: int = 0, offset_days: int = 0) -> dt.datetime:
    base = dt.datetime(2024, 1, 1)
    return base + dt.timedelta(hours=offset_hours, days=offset_days)


# ---------------------------------------------------------------------------
# extract_remaining_time_targets: mixed-type case-id guard
# ---------------------------------------------------------------------------


def test_extract_remaining_time_targets_rejects_mixed_type_case_ids() -> None:
    """Mixed int/str case_ids cannot be sorted; the function must raise TypeError
    with a clear message rather than silently producing wrong output.

    Mirrors the identical guard tests for extract_prefixes and
    extract_outcome_targets in test_prefixes.py.
    """
    events = [(1, "a", _ts(0)), ("c2", "b", _ts(1))]
    with pytest.raises(TypeError, match="same type"):
        list(extract_remaining_time_targets(events, [1, "c2"]))


# ---------------------------------------------------------------------------
# write_time_targets_csv / read_time_targets_csv round-trip
# ---------------------------------------------------------------------------


def test_round_trip_time_targets_csv(tmp_path) -> None:
    """All fields must survive a write-then-read cycle unchanged."""
    targets = [
        TimeTarget(case_id="c1", prefix_idx=1, remaining_days=2.5),
        TimeTarget(case_id="c1", prefix_idx=2, remaining_days=0.25),
        TimeTarget(case_id="c2", prefix_idx=1, remaining_days=0.0),
    ]
    path = str(tmp_path / "time.csv")
    n = write_time_targets_csv(targets, path)
    assert n == 3
    back = read_time_targets_csv(path)
    assert back == targets


def test_round_trip_time_targets_csv_gz(tmp_path) -> None:
    """Gzip-compressed output must round-trip identically to plain CSV."""
    targets = [TimeTarget(case_id="c1", prefix_idx=1, remaining_days=1.5)]
    path = str(tmp_path / "time.csv.gz")
    write_time_targets_csv(targets, path)
    back = read_time_targets_csv(path)
    assert back == targets


def test_round_trip_time_targets_csv_empty(tmp_path) -> None:
    """An empty write must read back as an empty list without error."""
    path = str(tmp_path / "empty.csv")
    n = write_time_targets_csv([], path)
    assert n == 0
    back = read_time_targets_csv(path)
    assert back == []


def test_time_targets_remaining_days_zero_roundtrips(tmp_path) -> None:
    """remaining_days=0.0 must survive the repr() encoding used by the writer."""
    targets = [TimeTarget(case_id="c1", prefix_idx=1, remaining_days=0.0)]
    path = str(tmp_path / "zero.csv")
    write_time_targets_csv(targets, path)
    back = read_time_targets_csv(path)
    assert back[0].remaining_days == 0.0


# ---------------------------------------------------------------------------
# write_outcome_targets_csv / read_outcome_targets_csv round-trip
# ---------------------------------------------------------------------------


def test_round_trip_outcome_targets_csv(tmp_path) -> None:
    """All fields must survive a write-then-read cycle unchanged."""
    targets = [
        OutcomeTarget(case_id="c1", prefix_idx=1, outcome=1),
        OutcomeTarget(case_id="c1", prefix_idx=2, outcome=1),
        OutcomeTarget(case_id="c2", prefix_idx=1, outcome=0),
    ]
    path = str(tmp_path / "outcome.csv")
    n = write_outcome_targets_csv(targets, path)
    assert n == 3
    back = read_outcome_targets_csv(path)
    assert back == targets


def test_round_trip_outcome_targets_csv_gz(tmp_path) -> None:
    """Gzip-compressed output must round-trip identically to plain CSV."""
    targets = [OutcomeTarget(case_id="c1", prefix_idx=1, outcome=0)]
    path = str(tmp_path / "outcome.csv.gz")
    write_outcome_targets_csv(targets, path)
    back = read_outcome_targets_csv(path)
    assert back == targets


def test_round_trip_outcome_targets_csv_empty(tmp_path) -> None:
    """An empty write must read back as an empty list without error."""
    path = str(tmp_path / "empty.csv")
    n = write_outcome_targets_csv([], path)
    assert n == 0
    back = read_outcome_targets_csv(path)
    assert back == []


def test_outcome_targets_both_classes_roundtrip(tmp_path) -> None:
    """outcome=1 and outcome=0 must both survive int encoding."""
    targets = [
        OutcomeTarget(case_id="pos", prefix_idx=1, outcome=1),
        OutcomeTarget(case_id="neg", prefix_idx=1, outcome=0),
    ]
    path = str(tmp_path / "both.csv")
    write_outcome_targets_csv(targets, path)
    back = read_outcome_targets_csv(path)
    assert back == targets
    assert all(isinstance(t.outcome, int) for t in back)
