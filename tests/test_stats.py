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


def test_summarize_top_activities_sorted_by_count_desc() -> None:
    s = summarize(_events(), top_n=10)
    counts = [c for _, c in s.top_activities]
    assert counts == sorted(counts, reverse=True)
    assert s.top_activities[0] == ("a", 2)


def test_summarize_top_transitions() -> None:
    s = summarize(_events())
    transitions = {pair: c for pair, c in s.top_transitions}
    assert transitions[("a", "b")] == 2  # c1 a→b and c2 a→b
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


def test_cli_stats_synthetic_toy() -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["stats", "synthetic-toy", "--top-n", "3"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["n_cases"] == 200
    assert data["n_events"] == 965
    assert len(data["top_activities"]) == 3
