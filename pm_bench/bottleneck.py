"""Bottleneck-detection targets - per-transition mean wait time.

Bottleneck is the only v0 task that's *per-transition* rather than
per-prefix: there's one truth row per ordered (activity_a, activity_b)
pair observed in the partition, with the mean wait time (seconds)
between them across all cases. Models predict a value per transition;
NDCG@10 over the ranking is the score.

Truth file columns:

    activity_a,activity_b,mean_wait_seconds,n_observations

Predictions file columns:

    activity_a,activity_b,predicted_wait_seconds
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from pm_bench.split import Activity, CaseId, Event


@dataclass(frozen=True)
class BottleneckTarget:
    activity_a: Activity
    activity_b: Activity
    mean_wait_seconds: float
    n_observations: int


@dataclass(frozen=True)
class BottleneckPrediction:
    activity_a: Activity
    activity_b: Activity
    predicted_wait_seconds: float


def extract_bottleneck_targets(
    events: Iterable[Event],
    case_ids: Iterable[CaseId],
) -> Iterator[BottleneckTarget]:
    """Yield per-transition mean wait time for the given case ids.

    For each pair of chronologically-consecutive activities within a
    case, we record the wait time. The yielded targets aggregate
    across all cases in `case_ids` - one row per distinct (a, b) pair.
    """
    keep = set(case_ids)
    by_case: dict[CaseId, list[tuple[Activity, object]]] = {}
    for case_id, activity, ts in events:
        if case_id not in keep:
            continue
        by_case.setdefault(case_id, []).append((activity, ts))

    sums: dict[tuple[Activity, Activity], float] = {}
    counts: dict[tuple[Activity, Activity], int] = {}
    for rows in by_case.values():
        rows.sort(key=lambda r: r[1])
        for (a, ta), (b, tb) in zip(rows, rows[1:], strict=False):
            key = (a, b)
            wait = (tb - ta).total_seconds()  # type: ignore[operator]
            sums[key] = sums.get(key, 0.0) + wait
            counts[key] = counts.get(key, 0) + 1

    for key in sorted(sums.keys()):
        yield BottleneckTarget(
            activity_a=key[0],
            activity_b=key[1],
            mean_wait_seconds=sums[key] / counts[key],
            n_observations=counts[key],
        )


def write_bottleneck_targets_csv(
    targets: Iterable[BottleneckTarget], path: str
) -> int:
    """Write bottleneck targets to a CSV file (plain or `.gz`)."""
    from pm_bench.predictions import _atomic_csv_write

    return _atomic_csv_write(
        path,
        ["activity_a", "activity_b", "mean_wait_seconds", "n_observations"],
        (
            (t.activity_a, t.activity_b, repr(t.mean_wait_seconds), t.n_observations)
            for t in targets
        ),
    )


def read_bottleneck_targets_csv(path: str) -> list[BottleneckTarget]:
    """Read a bottleneck-targets CSV (plain or `.gz`)."""
    import csv

    from pm_bench.predictions import _open_text, _require_field

    out: list[BottleneckTarget] = []
    with _open_text(path) as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r, start=2):
            a = _require_field(row, "activity_a", i, str(path)).strip()
            b = _require_field(row, "activity_b", i, str(path)).strip()
            mw = _require_field(row, "mean_wait_seconds", i, str(path))
            no = _require_field(row, "n_observations", i, str(path))
            out.append(
                BottleneckTarget(
                    activity_a=a,
                    activity_b=b,
                    mean_wait_seconds=float(mw),
                    n_observations=int(no),
                )
            )
    return out


def write_bottleneck_predictions_csv(
    predictions: Iterable[BottleneckPrediction], path: str
) -> int:
    """Write bottleneck predictions to a CSV file (plain or `.gz`)."""
    from pm_bench.predictions import _atomic_csv_write

    return _atomic_csv_write(
        path,
        ["activity_a", "activity_b", "predicted_wait_seconds"],
        (
            (p.activity_a, p.activity_b, repr(p.predicted_wait_seconds))
            for p in predictions
        ),
    )


def read_bottleneck_predictions_csv(path: str) -> list[BottleneckPrediction]:
    """Read a bottleneck-predictions CSV (plain or `.gz`)."""
    import csv

    from pm_bench.predictions import _open_text, _require_field

    out: list[BottleneckPrediction] = []
    with _open_text(path) as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r, start=2):
            a = _require_field(row, "activity_a", i, str(path)).strip()
            b = _require_field(row, "activity_b", i, str(path)).strip()
            pw = _require_field(row, "predicted_wait_seconds", i, str(path))
            out.append(
                BottleneckPrediction(
                    activity_a=a,
                    activity_b=b,
                    predicted_wait_seconds=float(pw),
                )
            )
    return out
