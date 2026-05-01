import hashlib

import pytest

from pm_bench.cache import cache_path
from pm_bench.fetch import (
    HashMismatchError,
    ManualFetchRequired,
    ensure_cached,
    sha256_file,
)
from pm_bench.registry import Dataset


def _ds(*, sha256: str | None = None, download_url: str | None = None) -> Dataset:
    return Dataset(
        name="demo",
        title="demo",
        cases=10,
        events=50,
        landing_url="https://example.invalid/landing",
        download_url=download_url,
        sha256=sha256,
        license="CC BY 4.0",
        format="xes",
        bundled=False,
    )


def _seed_cache(root, dataset: Dataset, payload: bytes) -> str:
    """Plant a fake archive in the cache; return its hex digest."""
    p = cache_path(dataset, override_root=str(root))
    p.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def test_sha256_file_matches_hashlib(tmp_path) -> None:
    f = tmp_path / "x"
    f.write_bytes(b"hello world")
    assert sha256_file(f) == hashlib.sha256(b"hello world").hexdigest()


def test_ensure_cached_no_url_no_file_raises_manual(tmp_path) -> None:
    d = _ds()
    with pytest.raises(ManualFetchRequired) as exc:
        ensure_cached(d, override_root=str(tmp_path))
    assert exc.value.dataset is d
    assert exc.value.expected_path.name == "demo.xes.gz"


def test_ensure_cached_unpinned_returns_actual_hash(tmp_path) -> None:
    d = _ds(sha256=None)
    digest = _seed_cache(tmp_path, d, b"fake archive contents")
    r = ensure_cached(d, override_root=str(tmp_path))
    assert r.sha256 == digest
    assert r.pinned is False
    assert r.downloaded is False


def test_ensure_cached_pinned_match_returns_pinned(tmp_path) -> None:
    payload = b"fake archive contents"
    digest = hashlib.sha256(payload).hexdigest()
    d = _ds(sha256=digest)
    _seed_cache(tmp_path, d, payload)
    r = ensure_cached(d, override_root=str(tmp_path))
    assert r.pinned is True
    assert r.sha256 == digest


def test_ensure_cached_pinned_mismatch_raises(tmp_path) -> None:
    d = _ds(sha256="0" * 64)
    _seed_cache(tmp_path, d, b"different contents")
    with pytest.raises(HashMismatchError) as exc:
        ensure_cached(d, override_root=str(tmp_path))
    assert "expected: " + ("0" * 64) in str(exc.value)


def test_ensure_cached_auto_downloads_from_url(tmp_path) -> None:
    """Spin up a one-shot HTTP server and fetch through `ensure_cached`."""
    import hashlib
    import http.server
    import os
    import socketserver
    import threading

    payload = b"fake archive served over http"
    digest = hashlib.sha256(payload).hexdigest()
    served_dir = tmp_path / "served"
    served_dir.mkdir()
    (served_dir / "log.xes.gz").write_bytes(payload)

    quiet_handler = type(
        "QuietHandler",
        (http.server.SimpleHTTPRequestHandler,),
        {"log_message": lambda *a, **kw: None},  # silence access logs
    )

    class _ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    httpd = _ThreadedHTTPServer(("127.0.0.1", 0), quiet_handler)
    port = httpd.server_address[1]
    cwd_before = os.getcwd()
    os.chdir(served_dir)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        d = _ds(
            sha256=digest,
            download_url=f"http://127.0.0.1:{port}/log.xes.gz",
        )
        cache_root = tmp_path / "cache"
        r = ensure_cached(d, override_root=str(cache_root))
        assert r.downloaded is True
        assert r.pinned is True
        assert r.sha256 == digest
        # Second call: cache hit, no re-download.
        r2 = ensure_cached(d, override_root=str(cache_root))
        assert r2.downloaded is False
    finally:
        httpd.shutdown()
        httpd.server_close()
        os.chdir(cwd_before)


def test_ensure_cached_synthetic_rejected(tmp_path) -> None:
    d = Dataset(
        name="syn",
        title="synthetic",
        cases=1,
        events=1,
        landing_url=None,
        download_url=None,
        sha256=None,
        license="MIT",
        format="synthetic",
        bundled=True,
    )
    with pytest.raises(Exception, match="generated on demand"):
        ensure_cached(d, override_root=str(tmp_path))
