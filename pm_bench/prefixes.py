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
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from pm_bench.split import Activity, CaseId, Event

PREFIX_SEP = "|"


@dataclass(frozen=True)
class Prefix:
    case_id: CaseId
    prefix_idx: int
    prefix: tuple[Activity, ...]
    true_next: Activity


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
