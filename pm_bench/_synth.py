"""Deterministic synthetic event log for the `synthetic-toy` dataset.

Five process variants modelling a small order-fulfillment workflow.
Cases are spread chronologically over a year so case-level chronological
splits behave realistically.
"""
from __future__ import annotations

import datetime as dt
import random
from collections.abc import Iterator

from pm_bench.split import Event

PATHS: list[list[str]] = [
    ["received", "payment_pending", "payment_settled", "allocate_inventory", "ship_order"],
    ["received", "payment_pending", "payment_settled", "refund_initiated"],
    [
        "received",
        "payment_pending",
        "fraud_review",
        "payment_settled",
        "allocate_inventory",
        "ship_order",
    ],
    ["received", "cancelled"],
    [
        "received",
        "payment_pending",
        "payment_settled",
        "allocate_inventory",
        "ship_order",
        "delivery_confirmed",
    ],
]
WEIGHTS: list[float] = [0.50, 0.15, 0.15, 0.10, 0.10]


def synthetic_log(n_cases: int = 50, seed: int = 42) -> Iterator[Event]:
    """Yield `(case_id, activity, timestamp)` tuples deterministically."""
    rng = random.Random(seed)
    start = dt.datetime(2024, 1, 1)
    span_days = 365
    for case_id in range(n_cases):
        path = rng.choices(PATHS, weights=WEIGHTS, k=1)[0]
        case_start = start + dt.timedelta(days=case_id * span_days // max(n_cases, 1))
        t = case_start
        for activity in path:
            yield (str(case_id), activity, t)
            t += dt.timedelta(hours=rng.randint(1, 48))
