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


def test_synthetic_seed_suffix_changes_split() -> None:
    """`synthetic-toy@<seed>` runs the generator at that seed."""
    runner = CliRunner()
    r1 = runner.invoke(main, ["split", "synthetic-toy"])
    r2 = runner.invoke(main, ["split", "synthetic-toy@99"])
    assert r1.exit_code == 0
    assert r2.exit_code == 0
    # Different seeds → different test partitions (case ids overlap, but
    # the path each takes is different, so the prefix counts differ).
    import json as _json
    assert r1.output != r2.output
    d1 = _json.loads(r1.output)
    d2 = _json.loads(r2.output)
    # Total case count is identical (n_cases default = 200).
    assert sum(d1["sizes"].values()) == sum(d2["sizes"].values()) == 200


def test_synthetic_seed_bad_int_fails_clearly() -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["split", "synthetic-toy@not-an-int"])
    assert r.exit_code == 1
    assert "bad seed" in r.output


def test_read_csv_log_strips_utf8_bom(tmp_path: Path) -> None:
    """Excel-exported CSVs carry a UTF-8 BOM; column resolution must
    still find `case_id` rather than getting `\\ufeffcase_id`."""
    p = tmp_path / "bom.csv"
    p.write_bytes(
        b"\xef\xbb\xbfcase_id,activity,timestamp\n"
        b"c1,a,2024-01-01T00:00:00\n"
    )
    events = read_csv_log(p)
    assert events == [("c1", "a", events[0][2])]


def test_read_csv_log_normalizes_tz_aware_timestamps(tmp_path: Path) -> None:
    """Mixed tz-aware + tz-naive rows must not blow up downstream."""
    p = tmp_path / "tz.csv"
    p.write_text(
        "case_id,activity,timestamp\n"
        "c1,a,2024-01-01T00:00:00+00:00\n"
        "c1,b,2024-01-01T01:00:00\n"
    )
    events = read_csv_log(p)
    assert len(events) == 2
    # All timestamps should be naive after normalization, so subtraction works.
    assert events[1][2] - events[0][2]
    assert all(e[2].tzinfo is None for e in events)


def test_cli_score_reads_gzipped_predictions(tmp_path: Path) -> None:
    """`pm-bench score` must accept .csv.gz inputs (matches checked-in
    leaderboard predictions and CONTRIBUTING.md)."""
    runner = CliRunner()
    split_path = tmp_path / "split.json"
    prefixes_path = tmp_path / "prefixes.csv"
    preds_path = tmp_path / "predictions.csv.gz"

    r = runner.invoke(main, ["split", "synthetic-toy"])
    assert r.exit_code == 0
    split_path.write_text(r.output)

    r = runner.invoke(
        main,
        ["prefixes", "synthetic-toy", "--split", str(split_path), "--out", str(prefixes_path)],
    )
    assert r.exit_code == 0
    r = runner.invoke(
        main,
        [
            "predict", "synthetic-toy", "--split", str(split_path),
            "--prefixes", str(prefixes_path), "--out", str(preds_path),
            "--baseline", "markov",
        ],
    )
    assert r.exit_code == 0
    r = runner.invoke(
        main,
        ["score", str(preds_path), "--prefixes", str(prefixes_path)],
    )
    assert r.exit_code == 0, r.output
    assert "top1" in r.output
