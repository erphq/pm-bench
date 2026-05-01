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


def test_read_csv_log_strips_whitespace_in_columns(tmp_path: Path) -> None:
    """Spreadsheet exports often emit ` c1` rows alongside `c1` rows;
    without strip the two would be distinct case ids and silently
    halve every metric."""
    p = tmp_path / "padded.csv"
    p.write_text(
        "case_id,activity,timestamp\n"
        " c1, a ,2024-01-01T00:00:00\n"
        "c1,b,2024-01-01T01:00:00\n"
    )
    events = read_csv_log(p)
    # Both rows should resolve to the same case_id.
    assert events[0][0] == events[1][0] == "c1"
    assert events[0][1] == "a"


def test_read_csv_log_handles_long_activity_names(tmp_path: Path) -> None:
    """csv module's default 128 KiB per-field limit must not block
    legitimate event logs with verbose labels."""
    p = tmp_path / "long.csv"
    huge_activity = "x" * (200 * 1024)  # 200 KiB > default limit
    p.write_text(
        "case_id,activity,timestamp\n"
        f"c1,{huge_activity},2024-01-01T00:00:00\n"
    )
    events = read_csv_log(p)
    assert len(events[0][1]) == 200 * 1024


def test_predictions_csv_strips_case_id_whitespace(tmp_path: Path) -> None:
    """A spreadsheet-padded predictions CSV must join correctly against
    the truth file, not silently miss every row."""
    from pm_bench.predictions import read_predictions_csv

    p = tmp_path / "preds.csv"
    p.write_text(
        "case_id,prefix_idx,predictions\n"
        " c1,1,a|b\n"
        "c2 ,2,c|d\n"
    )
    rows = read_predictions_csv(str(p))
    assert rows[0].case_id == "c1"
    assert rows[1].case_id == "c2"


def test_split_no_longer_takes_task_flag() -> None:
    """The split is task-agnostic; `--task` was removed in round 8."""
    runner = CliRunner()
    r = runner.invoke(main, ["split", "synthetic-toy", "--task", "next-event"])
    assert r.exit_code != 0
    assert "No such option" in r.output


def test_split_output_omits_task_field() -> None:
    """Round-8 cleanup dropped the unused `task` field from split.json."""
    import json as _json

    runner = CliRunner()
    r = runner.invoke(main, ["split", "synthetic-toy"])
    assert r.exit_code == 0
    data = _json.loads(r.output)
    assert "task" not in data
    assert {"dataset", "sizes", "train", "val", "test"}.issubset(data.keys())


def test_info_accepts_synthetic_seed_suffix() -> None:
    """`info synthetic-toy@99` must resolve to the base entry like
    every other CLI verb does."""
    import json as _json

    runner = CliRunner()
    r = runner.invoke(main, ["info", "synthetic-toy@99"])
    assert r.exit_code == 0, r.output
    data = _json.loads(r.output)
    assert data["name"] == "synthetic-toy"


def test_predictions_csv_strips_ranked_activity_whitespace(tmp_path: Path) -> None:
    """A spreadsheet-padded ranked activity must round-trip clean
    against an unpadded truth file."""
    from pm_bench.predictions import read_predictions_csv

    p = tmp_path / "preds.csv"
    p.write_text(
        "case_id,prefix_idx,predictions\n"
        "c1,1, payment_pending |cancelled\n"
    )
    rows = read_predictions_csv(str(p))
    assert rows[0].ranked == ("payment_pending", "cancelled")


def test_prefixes_csv_strips_true_next_and_prefix(tmp_path: Path) -> None:
    """Same invariant for the truth file readers."""
    from pm_bench.prefixes import read_prefixes_csv

    p = tmp_path / "p.csv"
    p.write_text(
        "case_id,prefix_idx,prefix,true_next\n"
        "c1,2, a | b , c \n"
    )
    rows = read_prefixes_csv(str(p))
    assert rows[0].prefix == ("a", "b")
    assert rows[0].true_next == "c"


def test_read_csv_log_rejects_empty_case_id(tmp_path: Path) -> None:
    """Empty case_id silently aggregates rows into a phantom case."""
    p = tmp_path / "bad.csv"
    p.write_text(
        "case_id,activity,timestamp\n"
        ",a,2024-01-01T00:00:00\n"
    )
    import pytest as _pytest

    with _pytest.raises(ValueError, match="empty case_id"):
        read_csv_log(p)


def test_load_split_rejects_non_list_partitions(tmp_path: Path) -> None:
    """A split.json with `train: "c1"` (string) would silently iterate
    as characters when fed to set(case_ids). Reject up front."""
    import json as _json

    bad = tmp_path / "split.json"
    bad.write_text(_json.dumps({"train": "c1", "val": [], "test": []}))
    runner = CliRunner()
    r = runner.invoke(
        main,
        [
            "prefixes", "synthetic-toy",
            "--split", str(bad),
            "--out", str(tmp_path / "x.csv"),
        ],
    )
    assert r.exit_code == 2
    assert "must be a JSON array" in r.output


def test_fetch_accepts_synthetic_seed_suffix() -> None:
    """`fetch synthetic-toy@99` should match synthetic-toy semantics —
    'generated on demand, no fetch needed' — not error as 'unknown'."""
    runner = CliRunner()
    r = runner.invoke(main, ["fetch", "synthetic-toy@99"])
    assert r.exit_code == 0, r.output
    assert "generated on demand" in r.output


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


def test_read_csv_log_tz_aware_rows_converted_to_utc(tmp_path: Path) -> None:
    """A tz-aware row at +05:00 must become a UTC-instant naive value,
    not a wall-clock-stripped naive value (which would silently reorder
    the row relative to naive rows)."""
    p = tmp_path / "tz.csv"
    p.write_text(
        "case_id,activity,timestamp\n"
        "c1,a,2024-01-01T05:00:00+05:00\n"  # 00:00 UTC
        "c1,b,2024-01-01T01:00:00\n"  # naive 01:00
    )
    events = read_csv_log(p)
    # After UTC conversion: a → 2024-01-01T00:00 UTC, b → 2024-01-01T01:00.
    # If we'd done a naive replace, a would be 05:00 (after b).
    assert events[0][1] == "a"
    assert events[1][1] == "b"
    assert events[0][2] < events[1][2]


def test_predictions_csv_strips_bom(tmp_path: Path) -> None:
    """A predictions CSV saved by Excel carries a UTF-8 BOM. The shared
    _open_text reader must strip it the same way read_csv_log does."""
    from pm_bench.predictions import read_predictions_csv

    p = tmp_path / "preds.csv"
    p.write_bytes(
        b"\xef\xbb\xbfcase_id,prefix_idx,predictions\n"
        b"c1,1,a|b\n"
    )
    rows = read_predictions_csv(str(p))
    assert len(rows) == 1
    assert rows[0].case_id == "c1"  # not '﻿c1'


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
