"""Case-level chronological split - the only blessed split in pm-bench.

Train = oldest 70% of cases by start time, val = next 10%, test = newest
20%. No within-case leakage; suffix-aware downstream evaluation samples
prefixes from test cases only.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

CaseId = str
Activity = str
Event = tuple[CaseId, Activity, datetime]


@dataclass(frozen=True)
class Split:
    train: list[CaseId]
    val: list[CaseId]
    test: list[CaseId]

    def sizes(self) -> tuple[int, int, int]:
        return (len(self.train), len(self.val), len(self.test))


def case_chrono_split(
    events: Iterable[Event],
    *,
    train_frac: float = 0.7,
    val_frac: float = 0.1,
) -> Split:
    """Split case ids into train/val/test by case start time.

    Args:
        events: an iterable of `(case_id, activity, timestamp)` tuples.
        train_frac: fraction of cases (oldest by start time) for train.
        val_frac: fraction of cases (next-oldest) for val.

    Returns:
        A `Split` with case-id lists for train, val, and test.

    Raises:
        ValueError: if the fractions are invalid.
    """
    if not 0 < train_frac < 1:
        raise ValueError("train_frac must be in (0, 1)")
    if not 0 <= val_frac < 1:
        raise ValueError("val_frac must be in [0, 1)")
    if train_frac + val_frac >= 1:
        raise ValueError("train_frac + val_frac must be < 1")

    case_starts: dict[CaseId, datetime] = {}
    for case_id, _activity, ts in events:
        existing = case_starts.get(case_id)
        if existing is None or ts < existing:
            case_starts[case_id] = ts

    ordered = sorted(case_starts.keys(), key=lambda c: case_starts[c])
    n = len(ordered)
    if n == 0:
        return Split(train=[], val=[], test=[])
    n_train = int(n * train_frac)
    n_val = int(n * val_frac)
    return Split(
        train=ordered[:n_train],
        val=ordered[n_train : n_train + n_val],
        test=ordered[n_train + n_val :],
    )
