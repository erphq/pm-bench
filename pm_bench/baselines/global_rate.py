"""Constant-global-rate floor baseline for outcome prediction.

Predicts the same training-set positive rate for every prefix. Doesn't
condition on the trace at all — every prediction is identical, so AUC
collapses to 0.5 (all ranks tied → average rank for both classes).
The honest "I'm a constant" floor sitting below prior-ref.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from pm_bench.baselines.prior_outcome import OutcomePrediction
from pm_bench.prefixes import OutcomeTarget
from pm_bench.split import Activity, CaseId, Event


@dataclass(frozen=True)
class GlobalRateBaseline:
    positive_rate: float


def fit_global_rate(
    events: Iterable[Event],
    train_case_ids: Iterable[CaseId],
    is_positive: Callable[[list[Activity]], bool],
) -> GlobalRateBaseline:
    """Fraction of training cases that meet the positive rule (per case)."""
    keep = set(train_case_ids)
    by_case: dict[CaseId, list[tuple[Activity, object]]] = {}
    for case_id, activity, ts in events:
        if case_id in keep:
            by_case.setdefault(case_id, []).append((activity, ts))

    n_pos = 0
    n_total = 0
    for rows in by_case.values():
        rows.sort(key=lambda r: r[1])
        if len(rows) < 2:
            continue
        n_total += 1
        if is_positive([a for a, _ in rows]):
            n_pos += 1
    rate = n_pos / n_total if n_total else 0.0
    return GlobalRateBaseline(positive_rate=rate)


def predict_global_rate(
    model: GlobalRateBaseline,
    targets: Iterable[OutcomeTarget],
) -> list[OutcomePrediction]:
    """Constant prediction for every prefix."""
    return [
        OutcomePrediction(
            case_id=t.case_id,
            prefix_idx=t.prefix_idx,
            score=model.positive_rate,
        )
        for t in targets
    ]
