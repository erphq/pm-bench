"""Zero-remaining-time floor baseline.

Predicts 0 days of remaining time for every prefix. The absolute MAE
floor — any model that ties this isn't using time information at all.
Sits below `mean-time` on the leaderboard and gives the dumbest
possible reference number.
"""
from __future__ import annotations

from collections.abc import Iterable

from pm_bench.baselines.mean_time import TimePrediction
from pm_bench.prefixes import TimeTarget


def predict_zero_time(targets: Iterable[TimeTarget]) -> list[TimePrediction]:
    """Constant 0.0 for every prefix."""
    return [
        TimePrediction(case_id=t.case_id, prefix_idx=t.prefix_idx, predicted_days=0.0)
        for t in targets
    ]
