"""pm-bench — the open process-mining benchmark."""
from __future__ import annotations

__version__ = "0.1.0"

from pm_bench.registry import Dataset, get_dataset, load_registry
from pm_bench.score import NextEventScore, score_next_event
from pm_bench.split import Event, Split, case_chrono_split

__all__ = [
    "Dataset",
    "Event",
    "NextEventScore",
    "Split",
    "case_chrono_split",
    "get_dataset",
    "load_registry",
    "score_next_event",
]
