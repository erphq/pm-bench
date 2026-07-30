"""Quick summary stats for an event log.

Useful when inspecting a new dataset - n_cases, n_events, distinct
activity count, time span, top-N most-frequent activities and
transitions, mean / median / min / max / std-dev case length, and
mean / median / min / max / std-dev per-case duration in days. Pure
CPython; runs in the same process as the rest of pm-bench so it works
on `synthetic-toy`, any CSV path, and (eventually) any cached BPI log.
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
    std_dev_case_length: float
    min_case_length: int
    max_case_length: int
    singleton_cases: int
    top_activities: list[tuple[Activity, int]]
    top_transitions: list[tuple[tuple[Activity, Activity], int]]
    mean_case_duration_days: float
    median_case_duration_days: float
    std_dev_case_duration_days: float
    min_case_duration_days: float
    max_case_duration_days: float


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
    case_durations: list[float] = []
    for rows in by_case.values():
        rows.sort(key=lambda r: r[1])
        case_lengths.append(len(rows))
        for (a, _), (b, _) in zip(rows, rows[1:], strict=False):
            transition_counts[(a, b)] += 1
        duration = (
            (rows[-1][1] - rows[0][1]).total_seconds() / 86400.0
            if len(rows) >= 2
            else 0.0
        )
        case_durations.append(duration)

    span_days = 0.0
    if earliest is not None and latest is not None:
        span_days = (latest - earliest).total_seconds() / 86400.0

    n_events = sum(len(rows) for rows in by_case.values())
    n_cases = len(by_case)
    mean_len = statistics.fmean(case_lengths) if case_lengths else 0.0
    median_len = statistics.median(case_lengths) if case_lengths else 0.0
    std_dev_len = statistics.pstdev(case_lengths) if case_lengths else 0.0
    min_len = min(case_lengths) if case_lengths else 0
    max_len = max(case_lengths) if case_lengths else 0
    singleton_cases = sum(1 for n in case_lengths if n == 1)
    mean_dur = statistics.fmean(case_durations) if case_durations else 0.0
    median_dur = statistics.median(case_durations) if case_durations else 0.0
    std_dev_dur = statistics.pstdev(case_durations) if case_durations else 0.0
    min_dur = min(case_durations) if case_durations else 0.0
    max_dur = max(case_durations) if case_durations else 0.0

    return LogStats(
        n_events=n_events,
        n_cases=n_cases,
        n_activities=len(activity_counts),
        span_days=span_days,
        earliest=earliest,
        latest=latest,
        mean_case_length=mean_len,
        median_case_length=median_len,
        std_dev_case_length=std_dev_len,
        min_case_length=min_len,
        max_case_length=max_len,
        singleton_cases=singleton_cases,
        top_activities=_top_n_sorted(activity_counts, top_n),
        top_transitions=_top_n_sorted(transition_counts, top_n),
        mean_case_duration_days=mean_dur,
        median_case_duration_days=median_dur,
        std_dev_case_duration_days=std_dev_dur,
        min_case_duration_days=min_dur,
        max_case_duration_days=max_dur,
    )


def _top_n_sorted(counter: Counter, n: int) -> list:
    """Return the top-N items, sorted by count descending then by key."""
    return sorted(
        counter.items(),
        key=lambda kv: (-kv[1], kv[0]),
    )[:n]
