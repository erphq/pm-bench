"""Negative-path tests for the CLI: error messages and exit codes.

The success paths are covered by per-task suites; this file fills in the
"do the error branches actually fire?" gap. Every UsageError / sys.exit(1)
/ sys.exit(2) branch should have at least one regression here.
"""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from pm_bench.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_split(tmp_path: Path) -> Path:
    runner = CliRunner()
    r = runner.invoke(main, ["split", "synthetic-toy"])
    assert r.exit_code == 0
    p = tmp_path / "split.json"
    p.write_text(r.output)
    return p


def _write_prefixes(tmp_path: Path, task: str, split_path: Path) -> Path:
    runner = CliRunner()
    out = tmp_path / f"prefixes-{task}.csv"
    r = runner.invoke(
        main,
        [
            "prefixes", "synthetic-toy",
            "--split", str(split_path),
            "--out", str(out),
            "--task", task,
        ],
    )
    assert r.exit_code == 0, r.output
    return out


def test_predict_with_wrong_baseline_for_task_fails(tmp_path: Path) -> None:
    """Mismatched (task, baseline) pairs are usage errors with a clean message."""
    runner = CliRunner()
    split_path = _write_split(tmp_path)
    prefixes_path = _write_prefixes(tmp_path, "next-event", split_path)
    # `mean` is for remaining-time, not next-event.
    r = runner.invoke(
        main,
        [
            "predict", "synthetic-toy",
            "--split", str(split_path),
            "--prefixes", str(prefixes_path),
            "--out", str(tmp_path / "p.csv"),
            "--task", "next-event",
            "--baseline", "mean",
        ],
    )
    assert r.exit_code != 0
    assert "doesn't apply to next-event" in r.output


def test_predict_remaining_time_with_markov_fails(tmp_path: Path) -> None:
    runner = CliRunner()
    split_path = _write_split(tmp_path)
    prefixes_path = _write_prefixes(tmp_path, "remaining-time", split_path)
    r = runner.invoke(
        main,
        [
            "predict", "synthetic-toy",
            "--split", str(split_path),
            "--prefixes", str(prefixes_path),
            "--out", str(tmp_path / "p.csv"),
            "--task", "remaining-time",
            "--baseline", "markov",
        ],
    )
    assert r.exit_code != 0
    assert "doesn't apply to remaining-time" in r.output


def test_score_predictions_missing_rows_exits_2(tmp_path: Path) -> None:
    """If predictions.csv lacks rows that prefixes.csv requires, score
    must exit 2 with a clear "missing N target(s)" message."""
    runner = CliRunner()
    split_path = _write_split(tmp_path)
    prefixes_path = _write_prefixes(tmp_path, "next-event", split_path)
    # Make a 1-row predictions file — missing 157 / 158 targets.
    preds_path = tmp_path / "preds.csv"
    preds_path.write_text(
        "case_id,prefix_idx,predictions\n"
        "0,1,received|cancelled\n"
    )
    r = runner.invoke(
        main,
        ["score", str(preds_path), "--prefixes", str(prefixes_path)],
    )
    assert r.exit_code == 2
    assert "missing" in r.output


def test_score_with_duplicate_prediction_keys_exits_2(tmp_path: Path) -> None:
    """Duplicate (case_id, prefix_idx) in predictions silently overwrote
    in the lookup-build before the round-3 fix; now must fail loudly,
    naming the offending key so the user can find it in their CSV."""
    runner = CliRunner()
    split_path = _write_split(tmp_path)
    prefixes_path = _write_prefixes(tmp_path, "next-event", split_path)
    preds_path = tmp_path / "preds.csv"
    preds_path.write_text(
        "case_id,prefix_idx,predictions\n"
        "0,1,received|cancelled\n"
        "0,1,payment_pending|cancelled\n"  # duplicate key, different prediction
    )
    r = runner.invoke(
        main,
        ["score", str(preds_path), "--prefixes", str(prefixes_path)],
    )
    assert r.exit_code == 2
    assert "duplicate" in r.output.lower()
    # Round-5: the message must include the offending key.
    assert "('0', 1)" in r.output


def test_score_with_malformed_predictions_csv_exits_2(tmp_path: Path) -> None:
    """A predictions file with the wrong column header → exit 2, clean message."""
    runner = CliRunner()
    split_path = _write_split(tmp_path)
    prefixes_path = _write_prefixes(tmp_path, "next-event", split_path)
    preds_path = tmp_path / "preds.csv"
    preds_path.write_text("foo,bar,baz\n1,2,3\n")
    r = runner.invoke(
        main,
        ["score", str(preds_path), "--prefixes", str(prefixes_path)],
    )
    # KeyError → caught → exit 2
    assert r.exit_code == 2


def test_score_conformance_with_bad_model_json_exits_2(tmp_path: Path) -> None:
    runner = CliRunner()
    split_path = _write_split(tmp_path)
    bad_model = tmp_path / "model.json"
    bad_model.write_text(json.dumps({"transitions": "not-a-list"}))
    r = runner.invoke(
        main,
        [
            "score", str(bad_model),
            "--task", "conformance",
            "--dataset", "synthetic-toy",
            "--split", str(split_path),
        ],
    )
    assert r.exit_code == 2


def test_validate_on_non_json_file_exits_2(tmp_path: Path) -> None:
    """`pm-bench validate <not-a-json-file>` must surface a clean error,
    not raw-traceback with JSONDecodeError."""
    bad = tmp_path / "not-json.json"
    bad.write_text("this is plain text, not JSON")
    runner = CliRunner()
    r = runner.invoke(main, ["validate", str(bad)])
    assert r.exit_code == 2
    assert "not valid JSON" in r.output


def test_validate_on_non_object_json_exits_2(tmp_path: Path) -> None:
    """JSON arrays / scalars at the top level aren't boards."""
    bad = tmp_path / "list.json"
    bad.write_text("[1, 2, 3]")
    runner = CliRunner()
    r = runner.invoke(main, ["validate", str(bad)])
    assert r.exit_code == 2
    assert "must be an object" in r.output


def test_compare_on_non_board_json_exits_2(tmp_path: Path) -> None:
    """A valid JSON file that isn't a board (missing `entries`) must
    fail cleanly, not raw-traceback with KeyError."""
    bad = tmp_path / "not-a-board.json"
    bad.write_text(json.dumps({"foo": "bar"}))
    real = REPO_ROOT / "leaderboard" / "next-event" / "synthetic-toy.json"
    runner = CliRunner()
    r = runner.invoke(main, ["compare", str(bad), str(real)])
    assert r.exit_code == 2
    assert "not a leaderboard file" in r.output


def test_compare_on_non_json_file_exits_2(tmp_path: Path) -> None:
    bad = tmp_path / "garbage.json"
    bad.write_text("definitely not json")
    real = REPO_ROOT / "leaderboard" / "next-event" / "synthetic-toy.json"
    runner = CliRunner()
    r = runner.invoke(main, ["compare", str(bad), str(real)])
    assert r.exit_code == 2
    assert "not valid JSON" in r.output


def test_prefixes_with_malformed_split_exits_2(tmp_path: Path) -> None:
    """A split file missing required keys must exit 2 with a clear message."""
    bad_split = tmp_path / "split.json"
    bad_split.write_text(json.dumps({"foo": "bar"}))
    runner = CliRunner()
    r = runner.invoke(
        main,
        [
            "prefixes", "synthetic-toy",
            "--split", str(bad_split),
            "--out", str(tmp_path / "x.csv"),
        ],
    )
    assert r.exit_code == 2
    assert "missing required key(s)" in r.output


def test_prefixes_with_non_json_split_exits_2(tmp_path: Path) -> None:
    bad_split = tmp_path / "split.json"
    bad_split.write_text("not json")
    runner = CliRunner()
    r = runner.invoke(
        main,
        [
            "prefixes", "synthetic-toy",
            "--split", str(bad_split),
            "--out", str(tmp_path / "x.csv"),
        ],
    )
    assert r.exit_code == 2
    assert "not valid JSON" in r.output


def test_prefixes_to_nonexistent_dir_auto_creates(tmp_path: Path) -> None:
    """`--out a/b/c.csv` should auto-mkdir parent rather than tracebacking."""
    runner = CliRunner()
    split_path = _write_split(tmp_path)
    out_path = tmp_path / "deep" / "nested" / "missing" / "p.csv"
    r = runner.invoke(
        main,
        ["prefixes", "synthetic-toy", "--split", str(split_path), "--out", str(out_path)],
    )
    assert r.exit_code == 0, r.output
    assert out_path.exists()


def test_predict_with_bad_prefixes_csv_exits_2(tmp_path: Path) -> None:
    """`pm-bench predict` used to raw-traceback on a malformed prefixes
    file; now wrapped by _runtime_safe and exits 2."""
    runner = CliRunner()
    split_path = _write_split(tmp_path)
    bad_prefixes = tmp_path / "bad.csv"
    bad_prefixes.write_text("foo,bar\n1,2\n")  # wrong columns
    r = runner.invoke(
        main,
        [
            "predict", "synthetic-toy",
            "--split", str(split_path),
            "--prefixes", str(bad_prefixes),
            "--out", str(tmp_path / "out.csv"),
            "--baseline", "markov",
        ],
    )
    assert r.exit_code == 2
    assert "missing required column" in r.output


def test_discover_into_nonexistent_dir_creates_it(tmp_path: Path) -> None:
    """write_model_json now auto-creates parent dirs (matching the CSV
    writers via _atomic_csv_write)."""
    runner = CliRunner()
    split_path = _write_split(tmp_path)
    out_path = tmp_path / "deep" / "nested" / "missing" / "model.json"
    r = runner.invoke(
        main,
        [
            "discover", "synthetic-toy",
            "--split", str(split_path),
            "--out", str(out_path),
            "--baseline", "dfg",
        ],
    )
    assert r.exit_code == 0, r.output
    assert out_path.exists()


def test_compare_on_typeerror_input_exits_2(tmp_path: Path) -> None:
    """A JSON whose `entries` is a string (TypeError on iteration)
    must exit 2 cleanly, not raw-traceback."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "task": "next-event",
        "dataset": "x",
        "metric": "m",
        "entries": "not a list",
    }))
    real = REPO_ROOT / "leaderboard" / "next-event" / "synthetic-toy.json"
    runner = CliRunner()
    r = runner.invoke(main, ["compare", str(bad), str(real)])
    assert r.exit_code == 2
    assert "not a leaderboard file" in r.output


def test_discover_writes_gzipped_model_json(tmp_path: Path) -> None:
    """write_model_json now handles .json.gz."""
    import gzip as _gz
    import json as _json

    runner = CliRunner()
    split_path = _write_split(tmp_path)
    out_path = tmp_path / "model.json.gz"
    r = runner.invoke(
        main,
        [
            "discover", "synthetic-toy",
            "--split", str(split_path),
            "--out", str(out_path),
            "--baseline", "dfg",
        ],
    )
    assert r.exit_code == 0, r.output
    with _gz.open(out_path, "rt") as f:
        data = _json.load(f)
    assert "transitions" in data


def test_score_with_short_csv_row_exits_2(tmp_path: Path) -> None:
    """A predictions row missing a required column must surface as a
    clean exit-2 error, not raw-traceback."""
    runner = CliRunner()
    split_path = _write_split(tmp_path)
    prefixes_path = _write_prefixes(tmp_path, "next-event", split_path)
    preds_path = tmp_path / "preds.csv"
    # Row with only 2 fields (csv parser sets predictions=None).
    preds_path.write_text(
        "case_id,prefix_idx,predictions\n"
        "0,1\n"
    )
    r = runner.invoke(
        main,
        ["score", str(preds_path), "--prefixes", str(prefixes_path)],
    )
    assert r.exit_code == 2
    assert "missing required column" in r.output


def test_leaderboard_single_board_with_malformed_json_exits_2(tmp_path: Path) -> None:
    """`pm-bench leaderboard <task> <dataset>` on a malformed JSON used to
    raw-traceback (caught only FileNotFoundError). Now: exit 2."""
    import shutil

    src = REPO_ROOT / "leaderboard"
    dst = tmp_path / "leaderboard"
    shutil.copytree(src, dst)
    target = dst / "next-event" / "synthetic-toy.json"
    target.write_text("not valid json")
    runner = CliRunner()
    r = runner.invoke(
        main,
        ["leaderboard", "next-event", "synthetic-toy", "--repo-root", str(tmp_path)],
    )
    assert r.exit_code == 2
    assert "malformed" in r.output


def test_leaderboard_unknown_task_in_json_caught(tmp_path: Path) -> None:
    """A board JSON with a typo'd task (not in VALID_TASKS) must not
    fall through to the next-event format and crash on f-string."""
    import json
    import shutil

    src = REPO_ROOT / "leaderboard"
    dst = tmp_path / "leaderboard"
    shutil.copytree(src, dst)
    target = dst / "next-event" / "synthetic-toy.json"
    raw = json.loads(target.read_text())
    raw["task"] = "next_event"  # typo: underscore, not dash
    target.write_text(json.dumps(raw))
    runner = CliRunner()
    r = runner.invoke(
        main,
        ["leaderboard", "next-event", "synthetic-toy", "--repo-root", str(tmp_path)],
    )
    assert r.exit_code == 2
    assert "unknown task" in r.output


def test_validate_with_bad_repo_root_exits_2(tmp_path: Path) -> None:
    """`validate --repo-root` pointing somewhere without predictions
    must surface a clean message, not raw-traceback FileNotFoundError."""
    runner = CliRunner()
    real_board = REPO_ROOT / "leaderboard" / "next-event" / "synthetic-toy.json"
    r = runner.invoke(
        main,
        ["validate", str(real_board), "--repo-root", str(tmp_path)],
    )
    assert r.exit_code == 2
    assert "predictions" in r.output.lower()


def test_leaderboard_all_with_missing_predictions_exits_2(tmp_path: Path) -> None:
    """`--all --verify` with the leaderboard JSONs but no predictions/
    dir must report each missing file cleanly, not raw-traceback."""
    import shutil

    shutil.copytree(
        REPO_ROOT / "leaderboard",
        tmp_path / "leaderboard",
        ignore=shutil.ignore_patterns("predictions"),
    )
    runner = CliRunner()
    r = runner.invoke(
        main,
        ["leaderboard", "--all", "--verify", "--repo-root", str(tmp_path)],
    )
    assert r.exit_code == 2
    assert "predictions not found" in r.output


def test_leaderboard_all_markdown_with_verify_runs_both(tmp_path: Path) -> None:
    """`--all --markdown --verify` must actually run verify, not silently skip it."""
    import shutil

    src = REPO_ROOT / "leaderboard"
    dst = tmp_path / "leaderboard"
    shutil.copytree(src, dst)
    # Tamper with one entry's recorded score.
    target = dst / "next-event" / "synthetic-toy.json"
    raw = json.loads(target.read_text())
    raw["entries"][0]["score"]["top1"] = 0.111
    target.write_text(json.dumps(raw))

    runner = CliRunner()
    r = runner.invoke(
        main,
        [
            "leaderboard",
            "--all", "--markdown", "--verify",
            "--repo-root", str(tmp_path),
        ],
    )
    # verify should fire and exit 2 before any markdown is printed
    assert r.exit_code == 2
    assert "drift" in r.output.lower()
