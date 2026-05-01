"""Last-activity-conditioned reference baseline for outcome prediction.

For every (last_activity_in_prefix → case_outcome) pair observed on the
training cases, store the empirical positive rate. At test time, look
up the prefix's last activity and return its rate. This is the dumbest
baseline that uses *any* prefix information - a model that ties this
isn't conditioning on the trace at all.

Falls back to the global positive rate when a prefix ends in an
activity unseen during training.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from pm_bench.prefixes import OutcomeTarget
from pm_bench.split import Activity, CaseId, Event


@dataclass(frozen=True)
class PriorOutcomeBaseline:
    """Last-activity → positive rate, plus a global fallback."""

    by_last: dict[Activity, float]
    global_rate: float


@dataclass(frozen=True)
class OutcomePrediction:
    case_id: CaseId
    prefix_idx: int
    score: float


def fit_prior_outcome(
    events: Iterable[Event],
    train_case_ids: Iterable[CaseId],
    is_positive: Callable[[list[Activity]], bool],
) -> PriorOutcomeBaseline:
    """Aggregate per-last-activity outcome rates over training prefixes."""
    keep = set(train_case_ids)
    by_case: dict[CaseId, list[tuple[Activity, object]]] = {}
    for case_id, activity, ts in events:
        if case_id not in keep:
            continue
        by_case.setdefault(case_id, []).append((activity, ts))

    counts: dict[Activity, list[int]] = defaultdict(lambda: [0, 0])  # [pos, total]
    pos_cases = 0
    total_cases = 0
    for rows in by_case.values():
        rows.sort(key=lambda r: r[1])
        activities = [a for a, _ in rows]
        if len(activities) < 2:
            continue
        total_cases += 1
        outcome = 1 if is_positive(activities) else 0
        if outcome:
            pos_cases += 1
        for k in range(1, len(activities)):
            last = activities[k - 1]
            counts[last][1] += 1
            if outcome:
                counts[last][0] += 1

    by_last = {
        last: (pos / total) if total else 0.0
        for last, (pos, total) in counts.items()
    }
    global_rate = (pos_cases / total_cases) if total_cases else 0.0
    return PriorOutcomeBaseline(by_last=by_last, global_rate=global_rate)


def predict_prior_outcome(
    model: PriorOutcomeBaseline,
    targets: Iterable[OutcomeTarget],
    events_by_case: dict[CaseId, list[Activity]] | None = None,
) -> list[OutcomePrediction]:
    """Score each target by its prefix's last-activity training rate.

    `events_by_case` maps every case_id we'll be asked about to its
    full ordered activity list (test cases included). Looking up the
    prefix's last activity needs the full sequence; the targets file
    by itself only carries `(case_id, prefix_idx)`.
    """
    out: list[OutcomePrediction] = []
    for t in targets:
        score = model.global_rate
        if events_by_case is not None:
            seq = events_by_case.get(t.case_id)
            if seq is not None and t.prefix_idx <= len(seq):
                last = seq[t.prefix_idx - 1]
                score = model.by_last.get(last, model.global_rate)
        out.append(OutcomePrediction(case_id=t.case_id, prefix_idx=t.prefix_idx, score=score))
    return out


def write_outcome_predictions_csv(
    predictions: Iterable[OutcomePrediction],
    path: str,
) -> int:
    """Write outcome predictions to CSV (plain or `.gz`). Returns row count."""
    import csv

    from pm_bench.predictions import _open_text

    n = 0
    with _open_text(path, "wt") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "prefix_idx", "score"])
        for p in predictions:
            w.writerow([p.case_id, p.prefix_idx, repr(p.score)])
            n += 1
    return n


def read_outcome_predictions_csv(path: str) -> list[OutcomePrediction]:
    """Read an outcome predictions CSV (plain or `.gz`)."""
    import csv

    from pm_bench.predictions import _open_text

    out: list[OutcomePrediction] = []
    with _open_text(path) as f:
        r = csv.DictReader(f)
        for row in r:
            out.append(
                OutcomePrediction(
                    case_id=row["case_id"],
                    prefix_idx=int(row["prefix_idx"]),
                    score=float(row["score"]),
                )
            )
    return out
