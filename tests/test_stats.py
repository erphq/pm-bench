"""Tests for the summary-stats helper and CLI."""
from __future__ import annotations

import datetime as dt
import json

from click.testing import CliRunner

from pm_bench.cli import main
from pm_bench.stats import summarize


def _events() -> list[tuple[str, str, dt.datetime]]:
    base = dt.datetime(2024, 1, 1)
    return [
        ("c1", "a", base),
        ("c1", "b", base + dt.timedelta(hours=1)),
        ("c1", "c", base + dt.timedelta(hours=2)),
        ("c2", "a", base + dt.timedelta(days=1)),
        ("c2", "b", base + dt.timedelta(days=1, hours=1)),
        ("c3", "x", base + dt.timedelta(days=2)),
    ]


def test_summarize_basic_counts() -> None:
    s = summarize(_events())
    assert s.n_events == 6
    assert s.n_cases == 3
    assert s.n_activities == 4  # a, b, c, x


def test_summarize_case_lengths() -> None:
    s = summarize(_events())
    assert s.mean_case_length == (3 + 2 + 1) / 3
    assert s.median_case_length == 2


def test_summarize_min_max_case_lengths() -> None:
    s = summarize(_events())
    # cases: c1=3 events, c2=2 events, c3=1 event
    assert s.min_case_length == 1
    assert s.max_case_length == 3


def test_summarize_top_activities_sorted_by_count_desc() -> None:
    s = summarize(_events(), top_n=10)
    counts = [c for _, c in s.top_activities]
    assert counts == sorted(counts, reverse=True)
    assert s.top_activities[0] == ("a", 2)


def test_summarize_top_transitions() -> None:
    s = summarize(_events())
    transitions = {pair: c for pair, c in s.top_transitions}
    assert transitions[("a", "b")] == 2  # c1 a->b and c2 a->b
    assert transitions[("b", "c")] == 1


def test_summarize_top_n_caps() -> None:
    s = summarize(_events(), top_n=2)
    assert len(s.top_activities) == 2


def test_summarize_empty_log_is_safe() -> None:
    s = summarize([])
    assert s.n_events == 0
    assert s.n_cases == 0
    assert s.span_days == 0.0
    assert s.earliest is None


def test_summarize_empty_log_min_max_zero() -> None:
    s = summarize([])
    assert s.min_case_length == 0
    assert s.max_case_length == 0


def test_summarize_span_days_and_time_bounds() -> None:
    s = summarize(_events())
    base = dt.datetime(2024, 1, 1)
    assert s.earliest == base
    assert s.latest == base + dt.timedelta(days=2)
    assert abs(s.span_days - 2.0) < 1e-9


def test_summarize_single_event_span_zero() -> None:
    ts = dt.datetime(2024, 6, 1)
    s = summarize([("c1", "task", ts)])
    assert s.span_days == 0.0
    assert s.earliest == ts
    assert s.latest == ts
    assert s.n_cases == 1
    assert s.n_events == 1
    assert s.min_case_length == 1
    assert s.max_case_length == 1
    assert s.mean_case_length == 1.0


def test_summarize_tie_breaking_is_lexicographic() -> None:
    # In _events(): "a" appears 2 times, "b" appears 2 times (tie).
    # "c" appears 1 time, "x" appears 1 time (tie).
    # Ties are broken by lexicographic key order.
    s = summarize(_events(), top_n=10)
    assert s.top_activities[:2] == [("a", 2), ("b", 2)]
    assert s.top_activities[2:] == [("c", 1), ("x", 1)]


def test_cli_stats_synthetic_toy() -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["stats", "synthetic-toy", "--top-n", "3"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["n_cases"] == 200
    assert data["n_events"] == 965
    assert len(data["top_activities"]) == 3
    assert "min_case_length" in data
    assert "max_case_length" in data


def test_summarize_std_dev_empty_log() -> None:
    s = summarize([])
    assert s.std_dev_case_length == 0.0


def test_summarize_std_dev_single_case() -> None:
    ts = dt.datetime(2024, 6, 1)
    s = summarize([("c1", "a", ts), ("c1", "b", ts + dt.timedelta(hours=1))])
    # Only one case; population std dev of [2] is 0.
    assert s.std_dev_case_length == 0.0


def test_summarize_std_dev_uniform_cases() -> None:
    # Three cases, each with exactly 2 events: std dev must be 0.
    base = dt.datetime(2024, 1, 1)
    events = [
        ("c1", "a", base),
        ("c1", "b", base + dt.timedelta(hours=1)),
        ("c2", "a", base + dt.timedelta(days=1)),
        ("c2", "b", base + dt.timedelta(days=1, hours=1)),
        ("c3", "a", base + dt.timedelta(days=2)),
        ("c3", "b", base + dt.timedelta(days=2, hours=1)),
    ]
    s = summarize(events)
    assert s.std_dev_case_length == 0.0


def test_summarize_std_dev_case_length_value() -> None:
    import statistics

    # _events() gives case lengths [3, 2, 1] (order stable inside cases).
    s = summarize(_events())
    expected = statistics.pstdev([3, 2, 1])
    assert abs(s.std_dev_case_length - expected) < 1e-9


def test_cli_stats_std_dev_present() -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["stats", "synthetic-toy"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert "std_dev_case_length" in data
    assert isinstance(data["std_dev_case_length"], float)
    assert data["std_dev_case_length"] >= 0.0
