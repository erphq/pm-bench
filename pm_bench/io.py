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
from datetime import datetime
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
    """
    p = Path(path)
    opener = gzip.open if str(p).endswith(".gz") else open
    out: list[Event] = []
    with opener(p, "rt", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: CSV is empty or missing a header")
        case_col, act_col, ts_col = _resolve_columns(list(reader.fieldnames))
        for i, row in enumerate(reader, start=2):  # row 2 = first data row
            try:
                ts = datetime.fromisoformat(row[ts_col])
            except (KeyError, ValueError) as exc:
                raise ValueError(f"{path}:{i}: bad timestamp {row.get(ts_col)!r}") from exc
            out.append((row[case_col], row[act_col], ts))
    return out
