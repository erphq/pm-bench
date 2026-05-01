"""Local cache directory management for pm-bench."""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_CACHE = Path.home() / ".cache" / "pm-bench"


def cache_dir(override: Path | None = None) -> Path:
    """Return the cache root, creating it if it doesn't exist.

    Priority: *override* > ``$PM_BENCH_CACHE`` env var > ``~/.cache/pm-bench``.
    """
    if override is not None:
        root = override
    elif env := os.environ.get("PM_BENCH_CACHE"):
        root = Path(env)
    else:
        root = _DEFAULT_CACHE
    root.mkdir(parents=True, exist_ok=True)
    return root


def dataset_path(name: str, filename: str, override: Path | None = None) -> Path:
    """Return (and create) the per-dataset cache subdirectory path."""
    d = cache_dir(override) / name
    d.mkdir(parents=True, exist_ok=True)
    return d / filename
