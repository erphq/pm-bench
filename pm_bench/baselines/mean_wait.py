"""Train-mean-wait reference baseline for bottleneck detection.

For every (activity_a, activity_b) transition observed in the training
cases, store the mean wait time. At test time, predict that mean. Falls
back to the global training mean for transitions never seen during
training.

Identifies the "obvious" bottlenecks - transitions that were already
slow in training. A model that ties this isn't using any new
information from the test set.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pm_bench.bottleneck import BottleneckPrediction, BottleneckTarget, extract_bottleneck_targets
from pm_bench.split import Activity, CaseId, Event


@dataclass(frozen=True)
class MeanWaitBaseline:
    by_transition: dict[tuple[Activity, Activity], float]
    global_mean_seconds: float


def fit_mean_wait(
    events: Iterable[Event],
    train_case_ids: Iterable[CaseId],
) -> MeanWaitBaseline:
    """Per-transition mean wait time over training cases."""
    targets = list(extract_bottleneck_targets(events, train_case_ids))
    if not targets:
        return MeanWaitBaseline(by_transition={}, global_mean_seconds=0.0)

    by_transition = {
        (t.activity_a, t.activity_b): t.mean_wait_seconds for t in targets
    }
    # Weight global mean by observation count so common transitions dominate.
    total_wait = sum(t.mean_wait_seconds * t.n_observations for t in targets)
    total_obs = sum(t.n_observations for t in targets)
    global_mean = (total_wait / total_obs) if total_obs else 0.0
    return MeanWaitBaseline(by_transition=by_transition, global_mean_seconds=global_mean)


def predict_mean_wait(
    model: MeanWaitBaseline,
    targets: Iterable[BottleneckTarget],
) -> list[BottleneckPrediction]:
    """For each target transition, return the trained mean (or global fallback)."""
    out: list[BottleneckPrediction] = []
    for t in targets:
        key = (t.activity_a, t.activity_b)
        pred = model.by_transition.get(key, model.global_mean_seconds)
        out.append(
            BottleneckPrediction(
                activity_a=t.activity_a,
                activity_b=t.activity_b,
                predicted_wait_seconds=pred,
            )
        )
    return out
