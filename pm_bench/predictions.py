"""Predictions file format.

A submission writes one row per prediction target, joined to the truth
file (prefixes.csv) on `(case_id, prefix_idx)`:

    case_id,prefix_idx,predictions

`predictions` is a `|`-joined ranked list of candidate next activities,
best first. Top-1 is `predictions[0]`; top-3 is `predictions[:3]`.
"""
from __future__ import annotations

import csv
import gzip
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pm_bench.prefixes import PREFIX_SEP
from pm_bench.split import Activity, CaseId


@dataclass(frozen=True)
class Prediction:
    case_id: CaseId
    prefix_idx: int
    ranked: tuple[Activity, ...]


def _open_text(path: str, mode: str = "rt") -> Any:
    """Open a path for text I/O, transparently handling `.gz`.

    Used by every CSV reader/writer in pm-bench so the `score` CLI and
    the leaderboard rescore path share one opener — divergence between
    "what `pm-bench score` accepts" and "what `--verify` accepts" is
    impossible by construction.

    Reads use `utf-8-sig` (transparently strips a UTF-8 BOM that Excel
    likes to add on save). Writes use `utf-8` so output is portable
    regardless of the host's `locale.getencoding()` (Windows defaults
    to cp1252, which mojibakes non-ASCII activity names).

    For write modes, auto-creates the parent directory if missing — a
    typo like `--out preds_dir/preds.csv` shouldn't fail with
    FileNotFoundError when the user obviously meant for it to be
    created.
    """
    from pathlib import Path

    is_write = mode.startswith("w")
    if is_write:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8" if is_write else "utf-8-sig"
    if str(path).endswith(".gz"):
        return gzip.open(path, mode, newline="", encoding=encoding)
    return open(path, mode, newline="", encoding=encoding)


def write_predictions_csv(predictions: Iterable[Prediction], path: str) -> int:
    """Write predictions to a CSV file. Returns the number of rows.

    Raises ValueError if any activity name contains the `|` separator
    used to encode the ranked list. We surface this loudly rather than
    silently corrupting the round-trip.
    """
    n = 0
    with _open_text(path, "wt") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "prefix_idx", "predictions"])
        for p in predictions:
            for a in p.ranked:
                if not a:
                    raise ValueError(
                        "activity is empty string — round-trip would lose it "
                        "(empty string is the encoding's 'no activities' sentinel)"
                    )
                if PREFIX_SEP in a:
                    raise ValueError(
                        f"activity {a!r} contains the {PREFIX_SEP!r} separator "
                        "used to encode the ranked list — predictions would "
                        "round-trip corrupted. Rename the activity or use a "
                        "dataset-specific encoding."
                    )
            w.writerow([p.case_id, p.prefix_idx, PREFIX_SEP.join(p.ranked)])
            n += 1
    return n


def read_predictions_csv(path: str) -> list[Prediction]:
    """Read a predictions CSV (plain or `.gz`)."""
    out: list[Prediction] = []
    with _open_text(path) as f:
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
