import pytest

from pm_bench import load_registry
from pm_bench.registry import get_dataset


def test_registry_has_expected_datasets() -> None:
    names = {d.name for d in load_registry()}
    expected = {
        "bpi2012",
        "bpi2017",
        "bpi2018",
        "bpi2019",
        "bpi2020",
        "sepsis",
        "helpdesk",
        "synthetic-toy",
    }
    assert names == expected


def test_get_dataset_synthetic() -> None:
    d = get_dataset("synthetic-toy")
    assert d.format == "synthetic"
    assert d.bundled is True


def test_get_dataset_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_dataset("nope")


def test_dataset_event_counts_are_positive() -> None:
    for d in load_registry():
        assert d.cases > 0
        assert d.events > 0
