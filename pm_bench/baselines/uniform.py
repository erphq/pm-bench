"""Uniform-over-activities reference baseline for next-event prediction.

The simplest possible model that doesn't peek at the prefix at all: it
ranks every activity seen during training in lexicographic order and
returns that same list for every prediction target. Top-1 accuracy
collapses to 1/|activities| (modulo whichever activity sorts first); a
real model has to clear that floor or it isn't using the trace.

This baseline exists alongside `markov` to demonstrate the leaderboard
scales to multiple entries on the same (task, dataset) pair - and to
give an honest "did the trace help at all?" comparison number.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pm_bench.predictions import Prediction
from pm_bench.prefixes import Prefix
from pm_bench.split import Activity, CaseId, Event


@dataclass(frozen=True)
class UniformBaseline:
    """Just the sorted set of activities observed during training."""

    activities_sorted: tuple[Activity, ...]


def fit_uniform(events: Iterable[Event], train_case_ids: Iterable[CaseId]) -> UniformBaseline:
    """Collect the set of activities seen in the training partition."""
    keep = set(train_case_ids)
    seen: set[Activity] = set()
    for case_id, activity, _ts in events:
        if case_id in keep:
            seen.add(activity)
    return UniformBaseline(activities_sorted=tuple(sorted(seen)))


def predict_uniform(
    model: UniformBaseline, prefixes: Iterable[Prefix]
) -> list[Prediction]:
    """Same ranked list for every target - the entire activity vocab."""
    ranking = model.activities_sorted
    return [
        Prediction(case_id=p.case_id, prefix_idx=p.prefix_idx, ranked=ranking)
        for p in prefixes
    ]
