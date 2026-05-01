"""I/O helpers for external event logs.

CSV ingest: any file with three columns mappable to `case_id`, `activity`,
and `timestamp` (ISO 8601) loads as a `list[Event]` ready for
`case_chrono_split`. The column-name aliases match the conventions
used by PM4Py's CSV importer (`case:concept:name`, `concept:name`,
`time:timestamp`) so XES-derived CSVs work without manual renaming.
"""
from __future__ import annotations

import csv
import gzip
from datetime import datetime, timezone
from pathlib import Path

from pm_bench.split import Event

CASE_ALIASES = {"case_id", "case:concept:name", "case", "trace"}
ACTIVITY_ALIASES = {"activity", "concept:name", "event", "name"}
TIMESTAMP_ALIASES = {"timestamp", "time:timestamp", "time", "ts"}


def looks_like_path(name: str) -> bool:
    """Heuristic: treat `name` as a filesystem path, not a registry name.

    We deliberately don't `os.path.exists` first - typos should fail in
    the loader with a clear FileNotFoundError, not silently fall through
    to the registry.
    """
    return any(c in name for c in ("/", "\\")) or name.endswith(
        (".csv", ".csv.gz", ".tsv", ".tsv.gz")
    )


def _resolve_columns(fieldnames: list[str]) -> tuple[str, str, str]:
    """Map a CSV header to (case_col, activity_col, timestamp_col)."""

    def pick(aliases: set[str], role: str) -> str:
        for f in fieldnames:
            if f in aliases:
                return f
        raise ValueError(
            f"CSV is missing a {role} column (expected one of {sorted(aliases)!r}); "
            f"got header {fieldnames!r}"
        )

    return (
        pick(CASE_ALIASES, "case_id"),
        pick(ACTIVITY_ALIASES, "activity"),
        pick(TIMESTAMP_ALIASES, "timestamp"),
    )


def read_csv_log(path: str | Path) -> list[Event]:
    """Read a CSV / .csv.gz event log into Event tuples.

    The CSV must have a header. Columns are matched by name (PM4Py
    aliases supported). Timestamps are parsed via `datetime.fromisoformat`,
    which accepts ISO 8601 with seconds precision.

    Tolerates UTF-8 BOM (Excel-exported CSVs). Mixed tz-aware /
    tz-naive timestamps are normalized to naive — we don't model
    timezones, only relative ordering and durations.
    """
    p = Path(path)
    opener = gzip.open if str(p).endswith(".gz") else open
    out: list[Event] = []
    # `utf-8-sig` strips a leading BOM if present; otherwise behaves
    # like utf-8. Without this, an Excel-style BOM makes the first
    # column read back as `﻿case_id` and the alias resolution
    # fails with a misleading "missing case_id" error.
    with opener(p, "rt", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: CSV is empty or missing a header")
        case_col, act_col, ts_col = _resolve_columns(list(reader.fieldnames))
        for i, row in enumerate(reader, start=2):  # row 2 = first data row
            # Strip leading/trailing whitespace from the three columns we
            # consume. Spreadsheet exports routinely emit `" c1"` rows
            # alongside `"c1"` rows, which would otherwise become two
            # distinct case ids and silently halve every metric. Our own
            # writers never emit padded values, so this is a safe
            # round-trip narrowing of the input.
            cid_raw = row.get(case_col)
            act_raw = row.get(act_col)
            ts_raw_obj = row.get(ts_col)
            if cid_raw is None or act_raw is None or ts_raw_obj is None:
                raise ValueError(
                    f"{path}:{i}: short row — missing one of "
                    f"{case_col!r}/{act_col!r}/{ts_col!r}"
                )
            try:
                ts = datetime.fromisoformat(ts_raw_obj.strip())
            except ValueError as exc:
                raise ValueError(f"{path}:{i}: bad timestamp {ts_raw_obj!r}") from exc
            # Normalize away any tzinfo so a CSV mixing aware + naive
            # rows doesn't blow up later when we subtract two timestamps
            # in a split or duration calc. Convert to UTC first — a bare
            # `replace(tzinfo=None)` keeps the wall-clock value, which
            # silently reorders aware rows relative to naive ones.
            if ts.tzinfo is not None:
                ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
            cid = cid_raw.strip()
            act = act_raw.strip()
            # Empty activity is rejected at write time; reject on read
            # too so the contract is symmetric and the user catches the
            # data-quality issue before training.
            if not act:
                raise ValueError(f"{path}:{i}: empty activity")
            out.append((cid, act, ts))
    return out
