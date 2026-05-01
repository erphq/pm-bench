"""Scoring scripts for pm-bench tasks.

v0: next-event prediction (top-1 / top-3 accuracy), remaining-time
prediction (MAE in days), outcome prediction (AUC), bottleneck
detection (NDCG@10), and conformance checking (DFG fitness × precision).
"""
from __future__ import annotations

import math
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
    held-out prefixes, in days. We don't case-weight by length -
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


@dataclass(frozen=True)
class OutcomeScore:
    """AUC for binary outcome prediction.

    `auc` is the area under the ROC curve, computed via the rank-sum
    identity (no scipy / sklearn needed). Ties in the score get the
    average rank - so a model that predicts the same probability for
    every case scores 0.5 by construction.
    """

    auc: float
    n: int
    n_pos: int


def score_outcome(
    predictions: Sequence[float],
    truth: Sequence[int],
) -> OutcomeScore:
    """ROC AUC for binary outcome prediction.

    `predictions[i]` is the model's predicted P(outcome=1) for the
    i-th held-out target; `truth[i]` is the actual outcome (0 or 1).

    Implementation: sort by score ascending, assign average ranks for
    ties, then AUC = (sum_of_ranks_of_positives - n_pos*(n_pos+1)/2) /
    (n_pos * n_neg). Edge cases: if either class is missing, AUC is
    undefined; we return 0.5 in that degenerate case so the
    leaderboard doesn't NaN out a row.
    """
    if len(predictions) != len(truth):
        raise ValueError("predictions and truth must be the same length")
    if len(predictions) == 0:
        raise ValueError("nothing to score")

    n = len(predictions)
    n_pos = sum(1 for t in truth if t == 1)
    n_neg = n - n_pos

    if n_pos == 0 or n_neg == 0:
        return OutcomeScore(auc=0.5, n=n, n_pos=n_pos)

    # Indices sorted by predicted score ascending; ties get average ranks.
    order = sorted(range(n), key=lambda i: predictions[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and predictions[order[j + 1]] == predictions[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-based ranks
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1

    sum_pos_ranks = sum(ranks[i] for i in range(n) if truth[i] == 1)
    auc = (sum_pos_ranks - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return OutcomeScore(auc=auc, n=n, n_pos=n_pos)


@dataclass(frozen=True)
class ConformanceScore:
    """DFG-based conformance: fitness × precision → F-score.

    `fitness` is the fraction of test-case directly-follows transitions
    that exist in the submitted model. `precision` is the fraction of
    model transitions that the test cases actually use. `fscore` is the
    harmonic mean - 2fp / (f+p).

    This is a simpler conformance check than alignment-based replay
    (which needs a Petri net + token semantics), but it's enough to
    catch the obvious failure modes: a model with too few transitions
    fails fitness; a model with too many fails precision.
    """

    fitness: float
    precision: float
    fscore: float
    n_test_transitions: int  # observed in test
    n_model_transitions: int  # in the submitted model


def score_conformance(
    model_transitions: set[tuple[str, str]],
    test_transitions: set[tuple[str, str]],
) -> ConformanceScore:
    """DFG fitness × precision → F-score.

    `model_transitions` is the submitted model's directly-follows
    relation (a set of (a, b) pairs). `test_transitions` is the same
    relation observed on the held-out cases. Both are unweighted -
    we measure structural agreement, not frequency.
    """
    n_test = len(test_transitions)
    n_model = len(model_transitions)
    if n_test == 0 and n_model == 0:
        return ConformanceScore(0.0, 0.0, 0.0, 0, 0)

    overlap = test_transitions & model_transitions
    fitness = len(overlap) / n_test if n_test else 0.0
    precision = len(overlap) / n_model if n_model else 0.0
    fscore = (2 * fitness * precision) / (fitness + precision) if (fitness + precision) > 0 else 0.0

    return ConformanceScore(
        fitness=fitness,
        precision=precision,
        fscore=fscore,
        n_test_transitions=n_test,
        n_model_transitions=n_model,
    )


@dataclass(frozen=True)
class BottleneckScore:
    """NDCG@k for transition-bottleneck ranking.

    `ndcg_at_k` is the standard normalized DCG: predicted ranking's DCG
    divided by the ideal DCG (sorting transitions descending by true
    wait time). Higher is better; 1.0 is a perfect ranking. `k` is the
    cutoff used; `n_transitions` is the size of the truth set.
    """

    ndcg_at_k: float
    k: int
    n_transitions: int


def _dcg(relevances: Sequence[float]) -> float:
    """Discounted cumulative gain: sum(rel_i / log2(i + 2)) for i in 0..n-1."""
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def score_bottleneck(
    predictions: dict[tuple[str, str], float],
    truth: dict[tuple[str, str], float],
    *,
    k: int = 10,
) -> BottleneckScore:
    """NDCG@k for a transition-wait-time ranking.

    `predictions[(a, b)]` is the model's predicted wait time for the
    transition `a → b`; `truth[(a, b)]` is the actual mean wait time
    on the held-out partition. We rank truth transitions by predicted
    wait (descending), take the top k, and compute NDCG against the
    ideal ranking (truth sorted descending). Transitions present in
    truth but missing from predictions are scored 0 - a model that
    refuses to predict can't claim credit.
    """
    if not truth:
        raise ValueError("truth is empty - nothing to rank")
    if k <= 0:
        raise ValueError("k must be > 0")

    transitions = list(truth.keys())
    # Rank by predicted wait, descending. Missing predictions = -inf so
    # they sink to the bottom (and contribute their truth at low rank).
    transitions.sort(key=lambda t: predictions.get(t, float("-inf")), reverse=True)
    pred_top = transitions[:k]
    pred_relevances = [truth[t] for t in pred_top]

    # Ideal ranking sorts truth descending.
    ideal_top = sorted(truth.values(), reverse=True)[:k]

    dcg = _dcg(pred_relevances)
    idcg = _dcg(ideal_top)
    ndcg = dcg / idcg if idcg > 0 else 0.0
    return BottleneckScore(ndcg_at_k=ndcg, k=k, n_transitions=len(truth))


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
