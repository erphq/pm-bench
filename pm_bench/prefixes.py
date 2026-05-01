"""Prefix extraction - the bridge between split and score.

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

For outcome, the truth is a binary integer (the case's final 0/1
outcome, repeated for every prefix of that case so predictions can
condition on prefix length):

    case_id,prefix_idx,outcome

- all three formats share `case_id, prefix_idx` so models that handle
multiple tasks share most of the loader.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime

from pm_bench.split import Activity, CaseId, Event

PREFIX_SEP = "|"
SECONDS_PER_DAY = 86400.0


def _sorted_case_ids(keep: set):
    """Return case ids in a deterministic order, with a clear error on
    mixed-type input (which Python's `sorted` would TypeError on)."""
    try:
        return sorted(keep)
    except TypeError as exc:
        raise TypeError(
            "case_ids must all be the same type (the CLI always emits "
            f"strings); got mixed types — {exc}"
        ) from exc


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


@dataclass(frozen=True)
class OutcomeTarget:
    """Binary outcome prediction target.

    `outcome` is the case's final 0/1 outcome - defined per-dataset
    (synthetic-toy: 1 iff the case ends with `delivery_confirmed`).
    The same value is repeated across every prefix of a case so a model
    can score how its prediction sharpens as the prefix grows.
    """

    case_id: CaseId
    prefix_idx: int
    outcome: int


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

    # `sorted(keep)` is the deterministic-bytes lever: set iteration order
    # depends on PYTHONHASHSEED and the resulting CSV layout would diff
    # across regeneration runs. Scores are invariant to row order; bytes
    # aren't, so we sort.
    for case_id in _sorted_case_ids(keep):
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
    """Write prefixes to a CSV file (plain or `.gz`). Returns the number of rows.

    Raises ValueError if any activity name contains the `|` separator —
    same constraint as `write_predictions_csv`, since both columns
    encode an ordered activity list with `|`.
    """
    import csv

    from pm_bench.predictions import _open_text

    n = 0
    with _open_text(path, "wt") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "prefix_idx", "prefix", "true_next"])
        for p in prefixes:
            for a in (*p.prefix, p.true_next):
                if not a:
                    raise ValueError(
                        "activity is empty string — round-trip would lose it "
                        "(empty string is the encoding's 'no activities' sentinel)"
                    )
                if PREFIX_SEP in a:
                    raise ValueError(
                        f"activity {a!r} contains the {PREFIX_SEP!r} separator "
                        "used to encode the prefix list — prefixes would "
                        "round-trip corrupted."
                    )
            w.writerow([p.case_id, p.prefix_idx, PREFIX_SEP.join(p.prefix), p.true_next])
            n += 1
    return n


def read_prefixes_csv(path: str) -> list[Prefix]:
    """Read a prefixes CSV emitted by `write_prefixes_csv` (plain or `.gz`)."""
    import csv

    from pm_bench.predictions import _open_text

    out: list[Prefix] = []
    with _open_text(path) as f:
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

    # `sorted(keep)` is the deterministic-bytes lever: set iteration order
    # depends on PYTHONHASHSEED and the resulting CSV layout would diff
    # across regeneration runs. Scores are invariant to row order; bytes
    # aren't, so we sort.
    for case_id in _sorted_case_ids(keep):
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


def extract_outcome_targets(
    events: Iterable[Event],
    case_ids: Iterable[CaseId],
    is_positive: Callable[[list[Activity]], bool],
) -> Iterator[OutcomeTarget]:
    """Yield outcome targets for the given case ids.

    `is_positive` is the per-dataset rule that decides a case's outcome
    from its full activity sequence (in chronological order). Targets
    are emitted at every prefix length 1..L-1, all carrying the same
    case-level outcome - so a model predicts the same target with
    progressively more context.
    """
    keep = set(case_ids)
    by_case: dict[CaseId, list[tuple[Activity, datetime]]] = {}
    for case_id, activity, ts in events:
        if case_id not in keep:
            continue
        by_case.setdefault(case_id, []).append((activity, ts))

    # `sorted(keep)` is the deterministic-bytes lever: set iteration order
    # depends on PYTHONHASHSEED and the resulting CSV layout would diff
    # across regeneration runs. Scores are invariant to row order; bytes
    # aren't, so we sort.
    for case_id in _sorted_case_ids(keep):
        rows = by_case.get(case_id)
        if not rows or len(rows) < 2:
            continue
        rows.sort(key=lambda r: r[1])
        activities = [a for a, _ in rows]
        outcome = 1 if is_positive(activities) else 0
        for k in range(1, len(activities)):
            yield OutcomeTarget(case_id=case_id, prefix_idx=k, outcome=outcome)


def write_outcome_targets_csv(targets: Iterable[OutcomeTarget], path: str) -> int:
    """Write outcome targets to a CSV file (plain or `.gz`)."""
    import csv

    from pm_bench.predictions import _open_text

    n = 0
    with _open_text(path, "wt") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "prefix_idx", "outcome"])
        for t in targets:
            w.writerow([t.case_id, t.prefix_idx, t.outcome])
            n += 1
    return n


def read_outcome_targets_csv(path: str) -> list[OutcomeTarget]:
    """Read an outcome-targets CSV (plain or `.gz`)."""
    import csv

    from pm_bench.predictions import _open_text

    out: list[OutcomeTarget] = []
    with _open_text(path) as f:
        r = csv.DictReader(f)
        for row in r:
            out.append(
                OutcomeTarget(
                    case_id=row["case_id"],
                    prefix_idx=int(row["prefix_idx"]),
                    outcome=int(row["outcome"]),
                )
            )
    return out


def write_time_targets_csv(targets: Iterable[TimeTarget], path: str) -> int:
    """Write remaining-time targets to a CSV file (plain or `.gz`)."""
    import csv

    from pm_bench.predictions import _open_text

    n = 0
    with _open_text(path, "wt") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "prefix_idx", "remaining_days"])
        for t in targets:
            w.writerow([t.case_id, t.prefix_idx, repr(t.remaining_days)])
            n += 1
    return n


def read_time_targets_csv(path: str) -> list[TimeTarget]:
    """Read a remaining-time CSV (plain or `.gz`)."""
    import csv

    from pm_bench.predictions import _open_text

    out: list[TimeTarget] = []
    with _open_text(path) as f:
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
