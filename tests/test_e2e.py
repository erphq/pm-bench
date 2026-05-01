"""End-to-end smoke: split → prefixes → predict → score on synthetic-toy.

Locks the file format the leaderboard depends on. If this test changes
shape, leaderboard submissions break - bump the version and announce.
"""
from __future__ import annotations

import json

from click.testing import CliRunner

from pm_bench.cli import main


def test_full_pipeline_runs_and_scores(tmp_path) -> None:
    runner = CliRunner()
    split_path = tmp_path / "split.json"
    prefixes_path = tmp_path / "prefixes.csv"
    preds_path = tmp_path / "predictions.csv"

    r = runner.invoke(main, ["split", "synthetic-toy"])
    assert r.exit_code == 0, r.output
    split_path.write_text(r.output)

    r = runner.invoke(
        main,
        [
            "prefixes",
            "synthetic-toy",
            "--split",
            str(split_path),
            "--out",
            str(prefixes_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert prefixes_path.exists()

    r = runner.invoke(
        main,
        [
            "predict",
            "synthetic-toy",
            "--split",
            str(split_path),
            "--prefixes",
            str(prefixes_path),
            "--out",
            str(preds_path),
            "--baseline",
            "markov",
        ],
    )
    assert r.exit_code == 0, r.output

    r = runner.invoke(
        main,
        [
            "score",
            str(preds_path),
            "--prefixes",
            str(prefixes_path),
            "--task",
            "next-event",
        ],
    )
    assert r.exit_code == 0, r.output
    result = json.loads(r.output)
    assert result["task"] == "next-event"
    assert result["n"] > 0
    # Synthetic-toy has tight transitions; markov should clear 50% top-1.
    assert result["top1"] >= 0.5
    assert 0.0 <= result["top1"] <= 1.0
    assert result["top3"] >= result["top1"]
