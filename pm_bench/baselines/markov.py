"""First-order Markov reference baseline.

Counts (current_activity → next_activity) transitions on training cases
only, then ranks candidates by frequency. Falls back to the global
unigram distribution when a prefix ends in an activity unseen during
training. No smoothing — the leaderboard reports raw frequencies.

Why first-order: it's the dumbest model that has any business being on
the leaderboard, and it sets the floor any "real" sequence model has to
clear. A transformer that ties or loses to first-order Markov is
broken or overfit.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from pm_bench.predictions import Prediction
from pm_bench.prefixes import Prefix
from pm_bench.split import Activity, Event


@dataclass
class MarkovBaseline:
    transitions: dict[Activity, Counter[Activity]]
    unigram: Counter[Activity]

    def rank(self, last_activity: Activity | None) -> list[Activity]:
        """Return candidate next activities, best first."""
        if last_activity is not None and last_activity in self.transitions:
            counts = self.transitions[last_activity]
            if counts:
                return [a for a, _ in counts.most_common()]
        return [a for a, _ in self.unigram.most_common()]


def fit_markov(events: Iterable[Event], train_case_ids: Iterable[Activity]) -> MarkovBaseline:
    """Fit a first-order Markov model on the training cases only."""
    keep = set(train_case_ids)
    by_case: dict[Activity, list[tuple[Activity, object]]] = {}
    for case_id, activity, ts in events:
        if case_id not in keep:
            continue
        by_case.setdefault(case_id, []).append((activity, ts))

    transitions: dict[Activity, Counter[Activity]] = defaultdict(Counter)
    unigram: Counter[Activity] = Counter()
    for rows in by_case.values():
        rows.sort(key=lambda r: r[1])
        activities = [a for a, _ in rows]
        for a in activities:
            unigram[a] += 1
        for prev, nxt in zip(activities, activities[1:], strict=False):
            transitions[prev][nxt] += 1

    return MarkovBaseline(transitions=dict(transitions), unigram=unigram)


def predict_markov(model: MarkovBaseline, prefixes: Iterable[Prefix]) -> list[Prediction]:
    """Score each prefix with the Markov model."""
    out: list[Prediction] = []
    for p in prefixes:
        last = p.prefix[-1] if p.prefix else None
        ranked = model.rank(last)
        out.append(Prediction(case_id=p.case_id, prefix_idx=p.prefix_idx, ranked=tuple(ranked)))
    return out
