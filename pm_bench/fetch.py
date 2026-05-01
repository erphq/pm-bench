"""Dataset fetch + hash verification.

The four cases that matter:

1. **Cached + hash matches.** Nothing to do - return the cached path.
2. **Cached + hash mismatch.** Loud failure: someone modified the
   archive on disk, or the registry hash is wrong. Either way we
   refuse to proceed silently.
3. **Cached + registry hash unset.** First-time pin path. The caller
   can compute the hash via `--pin` and PR a registry update.
4. **Not cached.** If the dataset has a `download_url` we fetch it,
   verify the hash, and cache. If not (the BPI / Sepsis case, gated
   behind 4TU's interactive TOS) we print precise manual-fetch
   instructions and exit non-zero.

We deliberately do not auto-write the registry. Hash pins must land
via PR so the provenance is reviewable.
"""
from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from pm_bench.cache import cache_path
from pm_bench.registry import Dataset

CHUNK_BYTES = 1 << 20  # 1 MiB streaming reads


@dataclass(frozen=True)
class FetchResult:
    """Outcome of a `ensure_cached` call."""

    dataset: str
    path: Path
    sha256: str
    pinned: bool  # True iff registry already had a hash and it matched
    downloaded: bool  # True iff we just fetched it (not present before)


class FetchError(RuntimeError):
    """Raised when a dataset can't be made available locally."""


class HashMismatchError(FetchError):
    """Cached file is on disk but its hash doesn't match the registry."""


class ManualFetchRequired(FetchError):
    """Dataset has no `download_url` - user must download + place manually."""

    def __init__(self, dataset: Dataset, expected_path: Path):
        self.dataset = dataset
        self.expected_path = expected_path
        super().__init__(
            f"{dataset.name}: no download_url (TOS-gated). Visit "
            f"{dataset.landing_url}, accept the terms, and save the archive to "
            f"{expected_path}. Then re-run `pm-bench fetch {dataset.name} --pin` "
            f"to compute the sha256 and PR it into registry.yml."
        )


def sha256_file(path: Path) -> str:
    """Stream a file and return its hex sha256."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_BYTES):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    """Stream a URL into `dest` atomically (write to .part, rename).

    On a mid-transfer exception, the partial `.part` file is removed so
    a subsequent run starts clean rather than leaving an orphaned blob
    in the cache dir.

    Two parallel `pm-bench fetch` invocations of the same dataset must
    not corrupt each other's writes. We mix PID + a random suffix into
    the temp name so each process gets its own staging file; the final
    rename onto `dest` is the only contended step (and `Path.replace`
    is atomic on POSIX / Windows).
    """
    import os
    import uuid

    tmp = dest.parent / f"{dest.name}.{os.getpid()}-{uuid.uuid4().hex}.part"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url) as resp, open(tmp, "wb") as out:  # noqa: S310
            while chunk := resp.read(CHUNK_BYTES):
                out.write(chunk)
        tmp.replace(dest)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise


def ensure_cached(dataset: Dataset, override_root: str | None = None) -> FetchResult:
    """Make `dataset` available on disk, verify hash, return its path.

    Synthetic datasets are rejected - they're generated on demand and
    have no on-disk form.
    """
    if dataset.format == "synthetic":
        raise FetchError(f"{dataset.name} is generated on demand, not cached")

    path = cache_path(dataset, override_root=override_root)
    downloaded = False

    if not path.exists():
        if not dataset.download_url:
            raise ManualFetchRequired(dataset, path)
        _download(dataset.download_url, path)
        downloaded = True

    actual = sha256_file(path)

    if dataset.sha256 is None:
        # First-time-on-disk; nothing to verify against. Caller decides
        # whether to pin (--pin) or proceed unverified.
        return FetchResult(
            dataset=dataset.name,
            path=path,
            sha256=actual,
            pinned=False,
            downloaded=downloaded,
        )

    if actual != dataset.sha256:
        raise HashMismatchError(
            f"{dataset.name}: sha256 mismatch at {path}\n"
            f"  expected: {dataset.sha256}\n"
            f"  actual:   {actual}\n"
            f"Either the archive is corrupt or the pinned hash is wrong. "
            f"Delete the cached file to re-fetch, or open a PR to update the pin."
        )

    return FetchResult(
        dataset=dataset.name,
        path=path,
        sha256=actual,
        pinned=True,
        downloaded=downloaded,
    )
