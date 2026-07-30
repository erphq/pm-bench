"""Tests for per-case duration statistics in LogStats.

Case duration: time from the first event to the last event within a
single case, in days. Distinct from span_days, which covers the time
from the earliest event across ALL cases to the latest event across
ALL cases.
"""
from __future__ import annotations

import datetime as dt
import json
import statistics

from click.testing import CliRunner

from pm_bench.cli import main
from pm_bench.stats import summarize


def _ts(days: float = 0.0) -> dt.datetime:
    return dt.datetime(2024, 1, 1) + dt.timedelta(days=days)


# ---- unit tests -----------------------------------------------------------


def test_case_duration_singleton_is_zero() -> None:
    s = summarize([("c1", "a", _ts(0))])
    assert s.min_case_duration_days == 0.0
    assert s.max_case_duration_days == 0.0
    assert s.mean_case_duration_days == 0.0


def test_case_duration_two_events_one_day() -> None:
    events = [("c1", "start", _ts(0)), ("c1", "end", _ts(1))]
    s = summarize(events)
    assert abs(s.mean_case_duration_days - 1.0) < 1e-9
    assert abs(s.min_case_duration_days - 1.0) < 1e-9
    assert abs(s.max_case_duration_days - 1.0) < 1e-9


def test_case_duration_multiple_cases() -> None:
    events = [
        ("c1", "a", _ts(0)),
        ("c1", "b", _ts(2)),     # duration 2 days
        ("c2", "a", _ts(10)),
        ("c2", "b", _ts(10.5)), # duration 0.5 days
    ]
    s = summarize(events)
    assert abs(s.mean_case_duration_days - 1.25) < 1e-6
    assert abs(s.min_case_duration_days - 0.5) < 1e-6
    assert abs(s.max_case_duration_days - 2.0) < 1e-6


def test_case_duration_empty_log() -> None:
    s = summarize([])
    assert s.mean_case_duration_days == 0.0
    assert s.median_case_duration_days == 0.0
    assert s.std_dev_case_duration_days == 0.0
    assert s.min_case_duration_days == 0.0
    assert s.max_case_duration_days == 0.0


def test_case_duration_std_dev_zero_when_all_same() -> None:
    events = [
        ("c1", "a", _ts(0)), ("c1", "b", _ts(1)),
        ("c2", "a", _ts(5)), ("c2", "b", _ts(6)),
    ]
    s = summarize(events)
    assert s.std_dev_case_duration_days == 0.0


def test_case_duration_std_dev_value() -> None:
    events = [
        ("c1", "a", _ts(0)),  ("c1", "b", _ts(1)),  # duration 1
        ("c2", "a", _ts(5)),  ("c2", "b", _ts(8)),  # duration 3
        ("c3", "a", _ts(10)), ("c3", "b", _ts(12)), # duration 2
    ]
    s = summarize(events)
    assert abs(s.std_dev_case_duration_days - statistics.pstdev([1.0, 3.0, 2.0])) < 1e-9


def test_case_duration_median_value() -> None:
    events = [
        ("c1", "a", _ts(0)),  ("c1", "b", _ts(1)),   # duration 1
        ("c2", "a", _ts(5)),  ("c2", "b", _ts(10)),  # duration 5
        ("c3", "a", _ts(20)), ("c3", "b", _ts(23)),  # duration 3
    ]
    s = summarize(events)
    assert abs(s.median_case_duration_days - 3.0) < 1e-9


def test_case_duration_distinct_from_span_days() -> None:
    events = [
        ("c1", "a", _ts(0)),   ("c1", "b", _ts(1)),    # c1 duration: 1 day
        ("c2", "a", _ts(100)), ("c2", "b", _ts(101)),  # c2 duration: 1 day
    ]
    s = summarize(events)
    assert abs(s.span_days - 101.0) < 1e-6
    assert abs(s.mean_case_duration_days - 1.0) < 1e-6


def test_case_duration_out_of_order_events_corrected() -> None:
    events = [("c1", "end", _ts(2)), ("c1", "start", _ts(0))]
    s = summarize(events)
    assert abs(s.mean_case_duration_days - 2.0) < 1e-9


def test_case_duration_min_lte_median_lte_max() -> None:
    events = [
        ("c1", "a", _ts(0)),  ("c1", "b", _ts(1)),
        ("c2", "a", _ts(5)),  ("c2", "b", _ts(8)),
        ("c3", "a", _ts(10)), ("c3", "b", _ts(12)),
    ]
    s = summarize(events)
    assert s.min_case_duration_days <= s.median_case_duration_days
    assert s.median_case_duration_days <= s.max_case_duration_days


# ---- CLI integration tests ------------------------------------------------


def test_cli_stats_has_all_duration_fields() -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["stats", "synthetic-toy"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    for field in (
        "mean_case_duration_days",
        "median_case_duration_days",
        "std_dev_case_duration_days",
        "min_case_duration_days",
        "max_case_duration_days",
    ):
        assert field in data, f"missing field: {field}"
        assert isinstance(data[field], float), f"{field} must be float"


def test_cli_stats_duration_ordering_invariant() -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["stats", "synthetic-toy"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["min_case_duration_days"] <= data["mean_case_duration_days"]
    assert data["mean_case_duration_days"] <= data["max_case_duration_days"]
    assert data["std_dev_case_duration_days"] >= 0.0
