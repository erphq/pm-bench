"""Deterministic random-rank floor baseline for bottleneck detection.

Assigns each transition a deterministic pseudo-random score by hashing
its (a, b) pair with a fixed seed. Order is independent of training
data, so NDCG@10 hovers near 0.5 — the model that does *not* know
which transitions are slow.

The hash is stable across Python versions (sha256-based) so the
checked-in leaderboard predictions don't drift across CI runs.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable

from pm_bench.bottleneck import BottleneckPrediction, BottleneckTarget

SEED_TAG = b"pm-bench/random-rank/v1"


def _stable_score(a: str, b: str) -> float:
    """Deterministic 64-bit-ish float in [0, 1) from the (a, b) pair."""
    h = hashlib.sha256()
    h.update(SEED_TAG)
    h.update(a.encode("utf-8"))
    h.update(b"\x00")
    h.update(b.encode("utf-8"))
    # Take the first 8 bytes as an unsigned int → [0, 1).
    n = int.from_bytes(h.digest()[:8], "big", signed=False)
    return n / (1 << 64)


def predict_random_rank(targets: Iterable[BottleneckTarget]) -> list[BottleneckPrediction]:
    """Stable pseudo-random score per transition."""
    return [
        BottleneckPrediction(
            activity_a=t.activity_a,
            activity_b=t.activity_b,
            predicted_wait_seconds=_stable_score(t.activity_a, t.activity_b),
        )
        for t in targets
    ]
