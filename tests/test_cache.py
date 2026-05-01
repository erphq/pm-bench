
import pytest

from pm_bench.cache import cache_path, cache_root
from pm_bench.registry import Dataset


def _ds(name: str = "demo", fmt: str = "xes") -> Dataset:
    return Dataset(
        name=name,
        title="demo",
        cases=10,
        events=50,
        landing_url=None,
        download_url=None,
        sha256=None,
        license="CC BY 4.0",
        format=fmt,
        bundled=False,
    )


def test_cache_root_respects_explicit_override(tmp_path) -> None:
    root = cache_root(str(tmp_path / "explicit"))
    assert root == tmp_path / "explicit"
    assert root.is_dir()


def test_cache_root_respects_env_var(tmp_path, monkeypatch) -> None:
    target = tmp_path / "env"
    monkeypatch.setenv("PM_BENCH_CACHE", str(target))
    assert cache_root() == target
    assert target.is_dir()


def test_cache_root_default_when_unset(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("PM_BENCH_CACHE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    root = cache_root()
    assert root == tmp_path / ".cache" / "pm-bench"


def test_cache_path_uses_xes_gz_for_xes(tmp_path) -> None:
    p = cache_path(_ds(fmt="xes"), override_root=str(tmp_path))
    assert p.name == "demo.xes.gz"


def test_cache_path_uses_csv_for_csv(tmp_path) -> None:
    p = cache_path(_ds(fmt="csv"), override_root=str(tmp_path))
    assert p.name == "demo.csv"


def test_cache_path_rejects_synthetic(tmp_path) -> None:
    with pytest.raises(ValueError, match="generated on demand"):
        cache_path(_ds(fmt="synthetic"), override_root=str(tmp_path))


def test_cache_path_rejects_unknown_format(tmp_path) -> None:
    with pytest.raises(ValueError, match="unknown dataset format"):
        cache_path(_ds(fmt="parquet"), override_root=str(tmp_path))
