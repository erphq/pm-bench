"""Prefix extraction — the bridge between split and score.

For next-event prediction, every test case of length L generates L-1
prediction targets: prefixes of length 1..L-1, each paired with the
activity that actually came next. Per the suffix-aware split rule,
prefixes are only ever drawn from test cases (never train/val), so the
score is honest about what the model saw at training time.

The emitted format is a CSV with columns:

    case_id,prefix_idx,prefix,true_next

where `prefix_idx` is the (1-based) length of the prefix and `prefix`
is `|`-joined activity names. This is the lingua franca file that
predictions are written against.

For remaining-time, the truth is a single float (days from end of
prefix to end of case), and the file has columns:

    case_id,prefix_idx,remaining_days

— shape parallels the next-event format so models that handle both
tasks share most of the loader.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime

from pm_bench.split import Activity, CaseId, Event

PREFIX_SEP = "|"
SECONDS_PER_DAY = 86400.0


@dataclass(frozen=True)
class Prefix:
    case_id: CaseId
    prefix_idx: int
    prefix: tuple[Activity, ...]
    true_next: Activity


@dataclass(frozen=True)
class TimeTarget:
    """Remaining-time prediction target.

    `remaining_days` is the number of days from the end of the prefix
    (i.e., the timestamp of activity `prefix_idx-1`) to the timestamp
    of the case's last event. Always ≥ 0 by construction.
    """

    case_id: CaseId
    prefix_idx: int
    remaining_days: float


def extract_prefixes(
    events: Iterable[Event],
    case_ids: Iterable[CaseId],
) -> Iterator[Prefix]:
    """Yield prediction targets for the given case ids.

    Events are grouped by `case_id` and ordered by timestamp; for each
    case of length L, prefixes of length 1..L-1 are yielded together
    with the activity that follows. Cases of length < 2 are skipped
    silently (nothing to predict).
    """
    keep = set(case_ids)
    by_case: dict[CaseId, list[tuple[Activity, object]]] = {}
    for case_id, activity, ts in events:
        if case_id not in keep:
            continue
        by_case.setdefault(case_id, []).append((activity, ts))

    for case_id in keep:
        rows = by_case.get(case_id)
        if not rows or len(rows) < 2:
            continue
        rows.sort(key=lambda r: r[1])
        activities = [a for a, _ in rows]
        for k in range(1, len(activities)):
            yield Prefix(
                case_id=case_id,
                prefix_idx=k,
                prefix=tuple(activities[:k]),
                true_next=activities[k],
            )


def write_prefixes_csv(prefixes: Iterable[Prefix], path: str) -> int:
    """Write prefixes to a CSV file. Returns the number of rows."""
    import csv

    n = 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "prefix_idx", "prefix", "true_next"])
        for p in prefixes:
            w.writerow([p.case_id, p.prefix_idx, PREFIX_SEP.join(p.prefix), p.true_next])
            n += 1
    return n


def read_prefixes_csv(path: str) -> list[Prefix]:
    """Read a prefixes CSV emitted by `write_prefixes_csv`."""
    import csv

    out: list[Prefix] = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            prefix_str = row["prefix"]
            prefix = tuple(prefix_str.split(PREFIX_SEP)) if prefix_str else ()
            out.append(
                Prefix(
                    case_id=row["case_id"],
                    prefix_idx=int(row["prefix_idx"]),
                    prefix=prefix,
                    true_next=row["true_next"],
                )
            )
    return out


def extract_remaining_time_targets(
    events: Iterable[Event],
    case_ids: Iterable[CaseId],
) -> Iterator[TimeTarget]:
    """Yield remaining-time targets for the given case ids.

    Mirrors `extract_prefixes` shape: every case of length L produces
    L-1 targets at prefix lengths 1..L-1, each carrying the remaining
    time (days) from the prefix's last event to the case's last event.
    """
    keep = set(case_ids)
    by_case: dict[CaseId, list[tuple[Activity, datetime]]] = {}
    for case_id, activity, ts in events:
        if case_id not in keep:
            continue
        by_case.setdefault(case_id, []).append((activity, ts))

    for case_id in keep:
        rows = by_case.get(case_id)
        if not rows or len(rows) < 2:
            continue
        rows.sort(key=lambda r: r[1])
        last_ts = rows[-1][1]
        for k in range(1, len(rows)):
            prefix_end_ts = rows[k - 1][1]
            remaining = (last_ts - prefix_end_ts).total_seconds() / SECONDS_PER_DAY
            yield TimeTarget(
                case_id=case_id,
                prefix_idx=k,
                remaining_days=remaining,
            )


def write_time_targets_csv(targets: Iterable[TimeTarget], path: str) -> int:
    """Write remaining-time targets to a CSV file. Returns the number of rows."""
    import csv

    n = 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "prefix_idx", "remaining_days"])
        for t in targets:
            w.writerow([t.case_id, t.prefix_idx, repr(t.remaining_days)])
            n += 1
    return n


def read_time_targets_csv(path: str) -> list[TimeTarget]:
    """Read a remaining-time CSV emitted by `write_time_targets_csv`."""
    import csv

    out: list[TimeTarget] = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            out.append(
                TimeTarget(
                    case_id=row["case_id"],
                    prefix_idx=int(row["prefix_idx"]),
                    remaining_days=float(row["remaining_days"]),
                )
            )
    return out
