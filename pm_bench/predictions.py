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


def _require_field(row: dict, col: str, line: int, path: str) -> str:
    """Get a string field from a CSV row, erroring loudly if missing.

    `csv.DictReader` returns `None` for a column when a data row is
    shorter than the header — without this check, the next operation
    (`.strip()`, `int()`, `float()`) would `AttributeError` /
    `TypeError` and surface as an uncaught traceback.
    """
    v = row.get(col)
    if v is None:
        raise ValueError(f"{path}:{line}: missing required column {col!r}")
    return v


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
    """Write predictions to a CSV file (plain or `.gz`). Returns the row count.

    Raises ValueError if any activity name contains the `|` separator
    or is empty — those would silently corrupt the round-trip on read.
    Writes go through a `.tmp` file and atomic rename so a mid-write
    validation failure doesn't leave a half-written file behind.
    """
    return _atomic_csv_write(
        path,
        ["case_id", "prefix_idx", "predictions"],
        ((p.case_id, p.prefix_idx, _encode_ranked(p.ranked)) for p in predictions),
    )


def _encode_ranked(ranked: tuple[Activity, ...]) -> str:
    for a in ranked:
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
    return PREFIX_SEP.join(ranked)


def _atomic_csv_write(path: str, header: list[str], rows) -> int:
    """Write rows to `path` atomically: stage in a sibling tmp file,
    rename on success, unlink on failure.

    Without this, a mid-stream validation failure (empty / pipe-bearing
    activity) would leave a partial file at `path` from earlier rows.

    The tmp suffix is inserted *before* `.gz` so `_open_text` still sees
    a `.gz` ending and applies gzip encoding to the staging file —
    otherwise the rename produces a plain-text file at a `.gz` path,
    breaking every reader.

    PID + UUID are mixed into the tmp name so two concurrent writers to
    the same `path` don't clobber each other's staging file. The final
    `Path.replace` is the only contended op and it's atomic on POSIX
    and Windows.
    """
    import os
    import uuid
    from pathlib import Path

    p = str(path)
    stamp = f"{os.getpid()}-{uuid.uuid4().hex}"
    tmp = (
        f"{p[:-3]}.{stamp}.tmp.gz"
        if p.endswith(".gz")
        else f"{p}.{stamp}.tmp"
    )
    n = 0
    try:
        with _open_text(tmp, "wt") as f:
            w = csv.writer(f)
            w.writerow(header)
            for row in rows:
                w.writerow(row)
                n += 1
        Path(tmp).replace(path)
        return n
    except BaseException:
        # Clean up the staging file if it exists.
        try:
            Path(tmp).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def read_predictions_csv(path: str) -> list[Prediction]:
    """Read a predictions CSV (plain or `.gz`).

    Strips whitespace from `case_id` so a spreadsheet-padded predictions
    file doesn't silently fail to join against the truth file.
    """
    out: list[Prediction] = []
    with _open_text(path) as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r, start=2):
            cid = _require_field(row, "case_id", i, str(path)).strip()
            pidx = _require_field(row, "prefix_idx", i, str(path)).strip()
            ranked_str = _require_field(row, "predictions", i, str(path))
            # Strip every ranked-list activity. A spreadsheet-padded
            # ` payment_pending` would otherwise miss the truth's
            # `payment_pending`, silently scoring 0.
            ranked = (
                tuple(s.strip() for s in ranked_str.split(PREFIX_SEP))
                if ranked_str
                else ()
            )
            out.append(
                Prediction(
                    case_id=cid,
                    prefix_idx=int(pidx),
                    ranked=ranked,
                )
            )
    return out
