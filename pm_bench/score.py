"""Scoring scripts for pm-bench tasks. v0: next-event prediction."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class NextEventScore:
    top1: float
    top3: float
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
