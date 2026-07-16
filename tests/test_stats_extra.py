"""Extra coverage tests for stats.summarize() and the stats CLI.

Covers paths not exercised by test_stats.py:
- Events arriving in non-chronological order within a case (the internal
  sort must produce correct transitions).
- Transition tie-breaking: tuples sort lexicographically just like strings.
- top_n larger than the number of distinct items (returns all, no error).
- Looping traces (a -> b -> a) produce both forward and backward transitions.
- All events share the same activity (no transitions, n_activities = 1).
- `pm-bench stats <csv-path>` routes through the CSV loader, not the registry.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib

from click.testing import CliRunner

from pm_bench.cli import main
from pm_bench.stats import summarize

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts(offset_hours: int = 0, offset_days: int = 0) -> dt.datetime:
    base = dt.datetime(2024, 6, 1)
    return base + dt.timedelta(hours=offset_hours, days=offset_days)


# ---------------------------------------------------------------------------
# summarize() unit tests
# ---------------------------------------------------------------------------


def test_summarize_out_of_order_events_produce_correct_transitions() -> None:
    """Events within a case that arrive in reverse timestamp order must be
    sorted before transitions are computed.

    Chronological order: a (0h) -> b (1h) -> c (2h).
    Feeding them as c, a, b should produce transitions (a, b) and (b, c),
    not (c, a) or (b, c) derived from arrival order.
    """
    events = [
        ("c1", "c", _ts(2)),
        ("c1", "a", _ts(0)),
        ("c1", "b", _ts(1)),
    ]
    s = summarize(events)
    pairs = {p for p, _ in s.top_transitions}
    assert ("a", "b") in pairs, f"expected a->b after sort, got {pairs}"
    assert ("b", "c") in pairs, f"expected b->c after sort, got {pairs}"
    assert ("c", "a") not in pairs, f"c->a must not appear; got {pairs}"
    assert ("a", "c") not in pairs, f"a->c must not appear; got {pairs}"


def test_summarize_out_of_order_case_length_is_unaffected() -> None:
    """Arrival order must not affect the case-length count."""
    events = [
        ("c1", "z", _ts(5)),
        ("c1", "a", _ts(0)),
        ("c1", "m", _ts(2)),
    ]
    s = summarize(events)
    assert s.min_case_length == 3
    assert s.max_case_length == 3
    assert s.n_events == 3


def test_summarize_transition_tie_breaking_is_lexicographic() -> None:
    """When two transitions share the same count, the one whose (a, b) tuple
    is lexicographically smaller must appear first.

    Here c1 does x->y and c2 does a->b.  Both appear once.
    ("a", "b") < ("x", "y") so the expected order is (a, b), (x, y).
    """
    events = [
        ("c1", "x", _ts(0)),
        ("c1", "y", _ts(1)),
        ("c2", "a", _ts(0, 1)),
        ("c2", "b", _ts(1, 1)),
    ]
    s = summarize(events)
    pairs = [p for p, _ in s.top_transitions]
    assert pairs == [("a", "b"), ("x", "y")], (
        f"expected lexicographic order [('a','b'), ('x','y')], got {pairs}"
    )


def test_summarize_top_n_larger_than_distinct_items_returns_all() -> None:
    """Requesting top_n > number of distinct activities / transitions must
    not raise and must return all available items."""
    events = [
        ("c1", "alpha", _ts(0)),
        ("c1", "beta", _ts(1)),
    ]
    s = summarize(events, top_n=999)
    assert len(s.top_activities) == 2, "only 2 distinct activities"
    assert len(s.top_transitions) == 1, "only 1 distinct transition"


def test_summarize_looping_trace_produces_both_directions() -> None:
    """A trace a -> b -> a must produce transitions (a, b) and (b, a)."""
    events = [
        ("c1", "a", _ts(0)),
        ("c1", "b", _ts(1)),
        ("c1", "a", _ts(2)),
    ]
    s = summarize(events)
    t = {p: c for p, c in s.top_transitions}
    assert t.get(("a", "b")) == 1, f"expected (a,b):1, got {t}"
    assert t.get(("b", "a")) == 1, f"expected (b,a):1, got {t}"
    assert len(t) == 2, f"expected exactly 2 transitions, got {t}"


def test_summarize_all_same_activity_no_transitions() -> None:
    """When every event in every case shares one activity and each case has
    only one event, there are no transitions and n_activities is 1."""
    events = [
        ("c1", "step", _ts(0)),
        ("c2", "step", _ts(0, 1)),
        ("c3", "step", _ts(0, 2)),
    ]
    s = summarize(events)
    assert s.n_activities == 1
    assert s.top_transitions == []
    assert s.singleton_cases == 3


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_stats_csv_path(tmp_path: pathlib.Path) -> None:
    """pm-bench stats <path/to/log.csv> must load the file via the CSV reader
    (not the registry) and emit valid JSON stats.

    The path contains "/" so looks_like_path() returns True; the .csv
    suffix provides a second trigger. Both are tested implicitly here.
    """
    csv_file = tmp_path / "log.csv"
    base = dt.datetime(2024, 3, 1)
    lines = [
        "case_id,activity,timestamp",
        f"c1,start,{base.isoformat()}",
        f"c1,end,{(base + dt.timedelta(hours=1)).isoformat()}",
        f"c2,start,{(base + dt.timedelta(days=1)).isoformat()}",
    ]
    csv_file.write_text("\n".join(lines), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["stats", str(csv_file)])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["n_cases"] == 2
    assert data["n_events"] == 3
    assert data["n_activities"] == 2  # start, end
    assert data["min_case_length"] == 1
    assert data["max_case_length"] == 2


def test_cli_stats_csv_path_top_n_option(tmp_path: pathlib.Path) -> None:
    """--top-n is respected when loading from a CSV path."""
    csv_file = tmp_path / "multi.csv"
    base = dt.datetime(2024, 1, 1)
    lines = ["case_id,activity,timestamp"]
    for i, act in enumerate(["alpha", "beta", "gamma", "delta"]):
        lines.append(f"c{i},{act},{(base + dt.timedelta(days=i)).isoformat()}")
    csv_file.write_text("\n".join(lines), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["stats", str(csv_file), "--top-n", "2"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data["top_activities"]) == 2
