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
