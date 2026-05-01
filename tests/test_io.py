"""CSV ingest tests."""
from __future__ import annotations

import gzip
from pathlib import Path

import pytest
from click.testing import CliRunner

from pm_bench.cli import main
from pm_bench.io import looks_like_path, read_csv_log


def test_looks_like_path_for_csv_extension() -> None:
    assert looks_like_path("foo.csv")
    assert looks_like_path("dir/log.csv.gz")
    assert looks_like_path("/abs/path.tsv")
    assert not looks_like_path("synthetic-toy")
    assert not looks_like_path("bpi2020")


def test_read_csv_log_simple(tmp_path: Path) -> None:
    p = tmp_path / "log.csv"
    p.write_text(
        "case_id,activity,timestamp\n"
        "c1,a,2024-01-01T00:00:00\n"
        "c1,b,2024-01-01T01:00:00\n"
        "c2,a,2024-01-01T00:00:00\n"
    )
    events = read_csv_log(p)
    assert len(events) == 3
    assert events[0][0] == "c1"
    assert events[0][1] == "a"


def test_read_csv_log_pm4py_aliases(tmp_path: Path) -> None:
    """PM4Py-style headers (case:concept:name etc.) work without renames."""
    p = tmp_path / "log.csv"
    p.write_text(
        "case:concept:name,concept:name,time:timestamp\n"
        "c1,a,2024-01-01T00:00:00\n"
    )
    events = read_csv_log(p)
    assert len(events) == 1


def test_read_csv_log_gzipped(tmp_path: Path) -> None:
    p = tmp_path / "log.csv.gz"
    with gzip.open(p, "wt") as f:
        f.write("case_id,activity,timestamp\nc1,a,2024-01-01T00:00:00\n")
    events = read_csv_log(p)
    assert events == [("c1", "a", events[0][2])]


def test_read_csv_log_missing_column_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.csv"
    p.write_text("foo,bar,baz\n1,2,3\n")
    with pytest.raises(ValueError, match="case_id"):
        read_csv_log(p)


def test_read_csv_log_bad_timestamp_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.csv"
    p.write_text("case_id,activity,timestamp\nc1,a,not-a-date\n")
    with pytest.raises(ValueError, match="bad timestamp"):
        read_csv_log(p)


def test_cli_split_accepts_csv_path(tmp_path: Path) -> None:
    """`pm-bench split path/to/log.csv` works without registry plumbing."""
    p = tmp_path / "log.csv"
    p.write_text(
        "case_id,activity,timestamp\n"
        "c1,a,2024-01-01T00:00:00\n"
        "c1,b,2024-01-02T00:00:00\n"
        "c2,a,2024-01-03T00:00:00\n"
        "c2,b,2024-01-04T00:00:00\n"
        "c3,a,2024-01-05T00:00:00\n"
        "c3,b,2024-01-06T00:00:00\n"
    )
    runner = CliRunner()
    r = runner.invoke(main, ["split", str(p)])
    assert r.exit_code == 0, r.output
    assert "train" in r.output


def test_cli_unknown_name_errors_clearly() -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["split", "no-such-thing"])
    assert r.exit_code == 1
    assert "unknown dataset" in r.output or "v0 only" in r.output
