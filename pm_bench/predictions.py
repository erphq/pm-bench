"""Predictions file format.

A submission writes one row per prediction target, joined to the truth
file (prefixes.csv) on `(case_id, prefix_idx)`:

    case_id,prefix_idx,predictions

`predictions` is a `|`-joined ranked list of candidate next activities,
best first. Top-1 is `predictions[0]`; top-3 is `predictions[:3]`.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pm_bench.prefixes import PREFIX_SEP
from pm_bench.split import Activity, CaseId


@dataclass(frozen=True)
class Prediction:
    case_id: CaseId
    prefix_idx: int
    ranked: tuple[Activity, ...]


def write_predictions_csv(predictions: Iterable[Prediction], path: str) -> int:
    """Write predictions to a CSV file. Returns the number of rows."""
    import csv

    n = 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "prefix_idx", "predictions"])
        for p in predictions:
            w.writerow([p.case_id, p.prefix_idx, PREFIX_SEP.join(p.ranked)])
            n += 1
    return n


def read_predictions_csv(path: str) -> list[Prediction]:
    """Read a predictions CSV."""
    import csv

    out: list[Prediction] = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            ranked_str = row["predictions"]
            ranked = tuple(ranked_str.split(PREFIX_SEP)) if ranked_str else ()
            out.append(
                Prediction(
                    case_id=row["case_id"],
                    prefix_idx=int(row["prefix_idx"]),
                    ranked=ranked,
                )
            )
    return out
