"""TODO tests for pm_bench.fetch and pm_bench._cache (v0.1 milestone)."""
from __future__ import annotations

import pytest


def test_fetch_unknown_dataset_raises_key_error() -> None:
    # TODO: from pm_bench.fetch import fetch_dataset
    #   fetch_dataset("nonexistent_dataset") should raise KeyError
    pytest.skip("TODO (v0.1): implement fetch_dataset first")


def test_fetch_dataset_without_url_raises_value_error() -> None:
    # TODO: pick any dataset with download_url=null (e.g. "bpi2012")
    #   fetch_dataset("bpi2012") should raise ValueError
    pytest.skip("TODO (v0.1): implement fetch_dataset first")


def test_fetch_synthetic_toy_bundled() -> None:
    # TODO: synthetic-toy is bundled — decide and implement the behaviour
    #   for fetch_dataset("synthetic-toy") (return bundled path without HTTP)
    pytest.skip("TODO (v0.1): decide behaviour for bundled datasets")


def test_cache_dir_default_is_under_home() -> None:
    # TODO: from pm_bench._cache import cache_dir
    #   d = cache_dir()
    #   assert d.name == "pm-bench"
    pytest.skip("TODO (v0.1): implement _cache.cache_dir first")


def test_cache_dir_env_override(tmp_path, monkeypatch) -> None:
    # TODO: monkeypatch.setenv("PM_BENCH_CACHE", str(tmp_path))
    #   from pm_bench._cache import cache_dir
    #   assert cache_dir() == tmp_path
    pytest.skip("TODO (v0.1): implement _cache.cache_dir first")
