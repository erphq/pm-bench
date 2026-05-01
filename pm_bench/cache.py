"""Local cache directory for downloaded event logs.

Datasets land in `$PM_BENCH_CACHE` if set, else `~/.cache/pm-bench/`.
We never write inside the install tree — the cache survives uninstalls
and wheel rebuilds, and a single cache can be shared across virtualenvs.

The on-disk layout is one file per dataset:

    <cache_root>/<name>.<ext>

where `<ext>` is `xes.gz` for XES logs (the canonical 4TU
distribution form) and `csv` / `csv.gz` for CSV. The synthetic-toy
dataset is generated on demand and never touches the cache.
"""
from __future__ import annotations

import os
from pathlib import Path

from pm_bench.registry import Dataset


def cache_root(override: str | None = None) -> Path:
    """Return the cache root, creating it if needed.

    Resolution order: explicit `override`, then `$PM_BENCH_CACHE`, then
    `~/.cache/pm-bench/`. The directory is created on first call so
    callers don't have to.
    """
    if override:
        root = Path(override).expanduser()
    elif env := os.environ.get("PM_BENCH_CACHE"):
        root = Path(env).expanduser()
    else:
        root = Path.home() / ".cache" / "pm-bench"
    root.mkdir(parents=True, exist_ok=True)
    return root


_EXT_BY_FORMAT = {
    "xes": "xes.gz",
    "csv": "csv",
}


def cache_path(dataset: Dataset, override_root: str | None = None) -> Path:
    """Return the on-disk path where this dataset's archive lives.

    The path is purely a function of `(cache_root, name, format)`; we
    do not check whether the file actually exists. Callers should test
    `path.exists()` before reading.
    """
    if dataset.format == "synthetic":
        raise ValueError(f"{dataset.name} is generated on demand, not cached")
    ext = _EXT_BY_FORMAT.get(dataset.format)
    if ext is None:
        raise ValueError(f"unknown dataset format: {dataset.format}")
    return cache_root(override_root) / f"{dataset.name}.{ext}"
