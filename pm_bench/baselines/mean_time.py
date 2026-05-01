"""Mean-of-train reference baseline for remaining-time prediction.

For every training prefix, compute the remaining time (days). The
baseline's prediction for any test prefix is the mean of those
training remainings - a single global float, no conditioning. It's
the dumbest model that has any business being on the leaderboard;
anything that loses to it isn't using time information at all.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pm_bench.prefixes import (
    TimeTarget,
    extract_remaining_time_targets,
)
from pm_bench.split import Event


@dataclass(frozen=True)
class MeanTimeBaseline:
    mean_remaining_days: float


@dataclass(frozen=True)
class TimePrediction:
    case_id: str
    prefix_idx: int
    predicted_days: float


def fit_mean_time(
    events: Iterable[Event],
    train_case_ids: Iterable[str],
) -> MeanTimeBaseline:
    """Mean of the per-prefix remaining-time observed on training cases."""
    targets = list(extract_remaining_time_targets(events, train_case_ids))
    if not targets:
        return MeanTimeBaseline(mean_remaining_days=0.0)
    total = sum(t.remaining_days for t in targets)
    return MeanTimeBaseline(mean_remaining_days=total / len(targets))


def predict_mean_time(
    model: MeanTimeBaseline,
    targets: Iterable[TimeTarget],
) -> list[TimePrediction]:
    """Constant prediction for every prefix."""
    return [
        TimePrediction(
            case_id=t.case_id,
            prefix_idx=t.prefix_idx,
            predicted_days=model.mean_remaining_days,
        )
        for t in targets
    ]


def write_time_predictions_csv(predictions: Iterable[TimePrediction], path: str) -> int:
    """Write remaining-time predictions to CSV (plain or `.gz`). Returns row count.

    Rejects NaN / Inf at write time — score functions reject them too,
    but a baseline that produced one would otherwise round-trip a "valid"
    CSV that only fails at score time.
    """
    import math

    from pm_bench.predictions import _atomic_csv_write

    def _rows():
        for p in predictions:
            if not math.isfinite(p.predicted_days):
                raise ValueError(
                    f"predicted_days for ({p.case_id!r}, {p.prefix_idx}) "
                    f"is {p.predicted_days!r}; must be finite"
                )
            yield (p.case_id, p.prefix_idx, repr(p.predicted_days))

    return _atomic_csv_write(
        path,
        ["case_id", "prefix_idx", "predicted_days"],
        _rows(),
    )


def read_time_predictions_csv(path: str) -> list[TimePrediction]:
    """Read a remaining-time predictions CSV (plain or `.gz`)."""
    import csv

    from pm_bench.predictions import _open_text, _require_field

    out: list[TimePrediction] = []
    with _open_text(path) as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r, start=2):
            cid = _require_field(row, "case_id", i, str(path)).strip()
            pidx = _require_field(row, "prefix_idx", i, str(path)).strip()
            pd = _require_field(row, "predicted_days", i, str(path))
            out.append(
                TimePrediction(
                    case_id=cid,
                    prefix_idx=int(pidx),
                    predicted_days=float(pd),
                )
            )
    return out
