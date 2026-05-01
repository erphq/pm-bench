"""End-to-end + targeted tests for the conformance task."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from click.testing import CliRunner

from pm_bench import score_conformance
from pm_bench.cli import main
from pm_bench.conformance import extract_dfg, read_model_json, write_model_json
from pm_bench.leaderboard import load_board, verify

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFORMANCE_BOARD = REPO_ROOT / "leaderboard" / "conformance" / "synthetic-toy.json"


def _events() -> list[tuple[str, str, dt.datetime]]:
    base = dt.datetime(2024, 1, 1)
    return [
        ("c1", "a", base),
        ("c1", "b", base + dt.timedelta(hours=1)),
        ("c1", "c", base + dt.timedelta(hours=2)),
        ("c2", "a", base),
        ("c2", "b", base + dt.timedelta(hours=1)),
        ("c2", "d", base + dt.timedelta(hours=2)),
    ]


def test_extract_dfg_collects_all_consecutive_pairs() -> None:
    dfg = extract_dfg(_events(), ["c1", "c2"])
    assert ("a", "b") in dfg
    assert ("b", "c") in dfg
    assert ("b", "d") in dfg
    assert len(dfg) == 3


def test_extract_dfg_skips_singleton_cases() -> None:
    base = dt.datetime(2024, 1, 1)
    events = [("c1", "a", base)]  # length-1 case has no transitions
    dfg = extract_dfg(events, ["c1"])
    assert dfg == set()


def test_perfect_model_scores_one() -> None:
    truth = {("a", "b"), ("b", "c")}
    model = {("a", "b"), ("b", "c")}
    s = score_conformance(model, truth)
    assert s.fitness == 1.0
    assert s.precision == 1.0
    assert s.fscore == 1.0


def test_too_small_model_loses_fitness() -> None:
    truth = {("a", "b"), ("b", "c")}
    model = {("a", "b")}
    s = score_conformance(model, truth)
    assert s.fitness == 0.5
    assert s.precision == 1.0
    # F = 2 * 0.5 * 1 / 1.5
    assert abs(s.fscore - 2 / 3) < 1e-9


def test_too_big_model_loses_precision() -> None:
    truth = {("a", "b")}
    model = {("a", "b"), ("x", "y"), ("p", "q")}
    s = score_conformance(model, truth)
    assert s.fitness == 1.0
    assert abs(s.precision - 1 / 3) < 1e-9


def test_disjoint_model_scores_zero() -> None:
    truth = {("a", "b"), ("b", "c")}
    model = {("x", "y")}
    s = score_conformance(model, truth)
    assert s.fitness == 0.0
    assert s.precision == 0.0
    assert s.fscore == 0.0


def test_round_trip_model_json(tmp_path: Path) -> None:
    transitions = {("a", "b"), ("b", "c"), ("c", "a")}
    p = tmp_path / "m.json"
    n = write_model_json(transitions, p)
    assert n == 3
    back = read_model_json(p)
    assert back == transitions


def test_read_model_json_rejects_bad_shape(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"transitions": [["a"], ["b", "c"]]}))
    import pytest

    with pytest.raises(ValueError, match="2-element"):
        read_model_json(p)


def test_read_model_json_rejects_non_string_pair_elements(tmp_path: Path) -> None:
    """[['a', 1], ...] is structurally a 2-element list but would fail
    to overlap with the (string-string) truth DFG → silent fitness=0."""
    import pytest

    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"transitions": [["a", 1]]}))
    with pytest.raises(ValueError, match="\\[string, string\\]"):
        read_model_json(p)


def test_conformance_board_verifies() -> None:
    board = load_board(CONFORMANCE_BOARD)
    drifts = verify(board, repo_root=REPO_ROOT)
    assert drifts == [], drifts


def test_full_conformance_pipeline(tmp_path: Path) -> None:
    runner = CliRunner()
    split_path = tmp_path / "split.json"
    model_path = tmp_path / "model.json"

    r = runner.invoke(main, ["split", "synthetic-toy"])
    assert r.exit_code == 0
    split_path.write_text(r.output)

    r = runner.invoke(
        main,
        ["discover", "synthetic-toy", "--split", str(split_path),
         "--out", str(model_path), "--baseline", "dfg"],
    )
    assert r.exit_code == 0, r.output

    r = runner.invoke(
        main,
        ["score", str(model_path), "--task", "conformance",
         "--dataset", "synthetic-toy", "--split", str(split_path)],
    )
    assert r.exit_code == 0, r.output
    result = json.loads(r.output)
    assert result["task"] == "conformance"
    assert 0.0 <= result["fitness"] <= 1.0
    assert 0.0 <= result["precision"] <= 1.0
    assert 0.0 <= result["fscore"] <= 1.0
    # DFG baseline should achieve fitness 1 on synthetic-toy (every test
    # transition appears at training time too - same path distribution).
    assert result["fitness"] == 1.0


def test_score_conformance_requires_dataset_and_split() -> None:
    runner = CliRunner()
    r = runner.invoke(main, ["score", "/dev/null", "--task", "conformance"])
    assert r.exit_code == 1
    assert "--dataset" in r.output
