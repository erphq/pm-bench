"""Bottleneck-detection targets — per-transition mean wait time.

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
    across all cases in `case_ids` — one row per distinct (a, b) pair.
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
    """Write bottleneck targets to a CSV file."""
    import csv

    n = 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["activity_a", "activity_b", "mean_wait_seconds", "n_observations"])
        for t in targets:
            w.writerow([t.activity_a, t.activity_b, repr(t.mean_wait_seconds), t.n_observations])
            n += 1
    return n


def read_bottleneck_targets_csv(path: str) -> list[BottleneckTarget]:
    """Read a bottleneck-targets CSV."""
    import csv

    out: list[BottleneckTarget] = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            out.append(
                BottleneckTarget(
                    activity_a=row["activity_a"],
                    activity_b=row["activity_b"],
                    mean_wait_seconds=float(row["mean_wait_seconds"]),
                    n_observations=int(row["n_observations"]),
                )
            )
    return out


def write_bottleneck_predictions_csv(
    predictions: Iterable[BottleneckPrediction], path: str
) -> int:
    """Write bottleneck predictions to a CSV file."""
    import csv

    n = 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["activity_a", "activity_b", "predicted_wait_seconds"])
        for p in predictions:
            w.writerow([p.activity_a, p.activity_b, repr(p.predicted_wait_seconds)])
            n += 1
    return n


def read_bottleneck_predictions_csv(path: str) -> list[BottleneckPrediction]:
    """Read a bottleneck-predictions CSV."""
    import csv

    out: list[BottleneckPrediction] = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            out.append(
                BottleneckPrediction(
                    activity_a=row["activity_a"],
                    activity_b=row["activity_b"],
                    predicted_wait_seconds=float(row["predicted_wait_seconds"]),
                )
            )
    return out
