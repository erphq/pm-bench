"""Quick summary stats for an event log.

Useful when inspecting a new dataset - n_cases, n_events, distinct
activity count, time span, top-N most-frequent activities and
transitions, mean / median / min / max case length. Pure CPython; runs
in the same process as the rest of pm-bench so it works on
`synthetic-toy`, any CSV path, and (eventually) any cached BPI log.
"""
from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from pm_bench.split import Activity, CaseId, Event


@dataclass(frozen=True)
class LogStats:
    n_events: int
    n_cases: int
    n_activities: int
    span_days: float
    earliest: datetime | None
    latest: datetime | None
    mean_case_length: float
    median_case_length: float
    min_case_length: int
    max_case_length: int
    top_activities: list[tuple[Activity, int]]
    top_transitions: list[tuple[tuple[Activity, Activity], int]]


def summarize(events: Iterable[Event], *, top_n: int = 10) -> LogStats:
    """Compute summary stats from an event iterable.

    `events` is consumed once. Top-N lists are sorted by count
    descending; ties broken by lexicographic order.
    """
    by_case: dict[CaseId, list[tuple[Activity, datetime]]] = {}
    activity_counts: Counter[Activity] = Counter()
    earliest: datetime | None = None
    latest: datetime | None = None

    for case_id, activity, ts in events:
        by_case.setdefault(case_id, []).append((activity, ts))
        activity_counts[activity] += 1
        if earliest is None or ts < earliest:
            earliest = ts
        if latest is None or ts > latest:
            latest = ts

    transition_counts: Counter[tuple[Activity, Activity]] = Counter()
    case_lengths: list[int] = []
    for rows in by_case.values():
        rows.sort(key=lambda r: r[1])
        case_lengths.append(len(rows))
        for (a, _), (b, _) in zip(rows, rows[1:], strict=False):
            transition_counts[(a, b)] += 1

    span_days = 0.0
    if earliest is not None and latest is not None:
        span_days = (latest - earliest).total_seconds() / 86400.0

    n_events = sum(len(rows) for rows in by_case.values())
    n_cases = len(by_case)
    mean_len = statistics.fmean(case_lengths) if case_lengths else 0.0
    median_len = statistics.median(case_lengths) if case_lengths else 0.0
    min_len = min(case_lengths) if case_lengths else 0
    max_len = max(case_lengths) if case_lengths else 0

    return LogStats(
        n_events=n_events,
        n_cases=n_cases,
        n_activities=len(activity_counts),
        span_days=span_days,
        earliest=earliest,
        latest=latest,
        mean_case_length=mean_len,
        median_case_length=median_len,
        min_case_length=min_len,
        max_case_length=max_len,
        top_activities=_top_n_sorted(activity_counts, top_n),
        top_transitions=_top_n_sorted(transition_counts, top_n),
    )


def _top_n_sorted(counter: Counter, n: int) -> list:
    """Return the top-N items, sorted by count descending then by key."""
    return sorted(
        counter.items(),
        key=lambda kv: (-kv[1], kv[0]),
    )[:n]
