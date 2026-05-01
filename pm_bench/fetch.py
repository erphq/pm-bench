"""Fetch a registered dataset to the local cache."""
from __future__ import annotations

from pathlib import Path

# TODO (v0.1): implement HTTP download using requests or urllib.request:
#   - Resume support via Range header
#   - sha256 verification after download
#   - Atomic move from .tmp to final path


def fetch_dataset(name: str, cache_dir: Path | None = None) -> Path:
    """Download dataset *name* to *cache_dir* and return its local path.

    Parameters
    ----------
    name:
        Registry key, e.g. ``"bpi2012"``.
    cache_dir:
        Override for the cache root.  Defaults to ``~/.cache/pm-bench``.

    Returns
    -------
    Path
        Path to the downloaded file (XES or CSV).

    Raises
    ------
    KeyError
        If *name* is not in the registry.
    ValueError
        If the dataset has no ``download_url`` yet.
    NotImplementedError
        Until this function is implemented.
    """
    # TODO: call _cache.cache_dir() when cache_dir is None
    # TODO: look up dataset via registry.get_dataset(name); raise KeyError if unknown
    # TODO: raise ValueError if dataset.download_url is None
    # TODO: download to cache_dir / name / filename
    # TODO: verify sha256 if dataset.sha256 is set
    raise NotImplementedError("fetch_dataset is not yet implemented — see TODO.md")
