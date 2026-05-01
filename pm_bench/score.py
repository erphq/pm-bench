"""Scoring scripts for pm-bench tasks.

v0: next-event prediction (top-1 / top-3 accuracy) and remaining-time
prediction (MAE in days).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class NextEventScore:
    top1: float
    top3: float
    n: int


@dataclass(frozen=True)
class RemainingTimeScore:
    """MAE for remaining-time prediction.

    `mae_days` is the equally-weighted mean absolute error across all
    held-out prefixes, in days. We don't case-weight by length —
    every prefix is one prediction, every prediction counts once.
    Reporting `n` lets readers tell which split a number was computed
    against.
    """

    mae_days: float
    n: int


def score_next_event(
    predictions: Sequence[Sequence[str]],
    truth: Sequence[str],
) -> NextEventScore:
    """Top-k accuracy for next-event prediction.

    Each `predictions[i]` is a ranked list of candidate next activities
    for the i-th held-out prefix; `truth[i]` is what actually happened
    next. Returns top-1 and top-3 accuracy.
    """
    if len(predictions) != len(truth):
        raise ValueError("predictions and truth must be the same length")
    if len(predictions) == 0:
        raise ValueError("nothing to score")
    n = len(truth)
    top1 = sum(1 for pred, t in zip(predictions, truth, strict=True) if pred and pred[0] == t)
    top3 = sum(1 for pred, t in zip(predictions, truth, strict=True) if t in pred[:3])
    return NextEventScore(top1=top1 / n, top3=top3 / n, n=n)


def score_remaining_time(
    predictions: Sequence[float],
    truth: Sequence[float],
) -> RemainingTimeScore:
    """MAE in days for remaining-time prediction.

    `predictions[i]` is the model's predicted remaining time (days)
    for the i-th held-out prefix; `truth[i]` is what actually happened.
    """
    if len(predictions) != len(truth):
        raise ValueError("predictions and truth must be the same length")
    if len(predictions) == 0:
        raise ValueError("nothing to score")
    n = len(truth)
    total = sum(abs(float(p) - float(t)) for p, t in zip(predictions, truth, strict=True))
    return RemainingTimeScore(mae_days=total / n, n=n)
