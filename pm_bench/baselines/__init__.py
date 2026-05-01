"""Reference baselines that ship with pm-bench.

Baselines exist to anchor the leaderboard: a submission that loses to
the markov reference is an immediate red flag. They're deliberately
simple — no torch, no scikit-learn, no GPUs, just CPython — so anyone
can read the code and trust the number.
"""
from __future__ import annotations

from pm_bench.baselines.markov import MarkovBaseline, predict_markov
from pm_bench.baselines.mean_time import (
    MeanTimeBaseline,
    TimePrediction,
    fit_mean_time,
    predict_mean_time,
    read_time_predictions_csv,
    write_time_predictions_csv,
)
from pm_bench.baselines.prior_outcome import (
    OutcomePrediction,
    PriorOutcomeBaseline,
    fit_prior_outcome,
    predict_prior_outcome,
    read_outcome_predictions_csv,
    write_outcome_predictions_csv,
)

__all__ = [
    "MarkovBaseline",
    "MeanTimeBaseline",
    "OutcomePrediction",
    "PriorOutcomeBaseline",
    "TimePrediction",
    "fit_mean_time",
    "fit_prior_outcome",
    "predict_markov",
    "predict_mean_time",
    "predict_prior_outcome",
    "read_outcome_predictions_csv",
    "read_time_predictions_csv",
    "write_outcome_predictions_csv",
    "write_time_predictions_csv",
]
