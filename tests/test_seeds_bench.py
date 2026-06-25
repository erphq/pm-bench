"""Smoke tests for the cross-seed variance harness."""
from __future__ import annotations

import json

import pytest

from bench.seeds import TASKS, _run_one, main, render_markdown, variance


@pytest.mark.parametrize("task", TASKS)
def test_run_one_returns_a_metric(task: str) -> None:
    out = _run_one(seed=0, task=task)
    assert isinstance(out, dict)
    assert len(out) >= 1
    for v in out.values():
        assert isinstance(v, float)


def test_variance_n_seeds_fast() -> None:
    """N=2 to keep the test fast — still exercises the mean/std code paths."""
    out = variance("next-event", n_seeds=2)
    assert out["task"] == "next-event"
    assert out["n_seeds"] == 2
    metrics = out["metrics"]["top1"]
    assert "mean" in metrics
    assert "std" in metrics
    assert metrics["min"] <= metrics["mean"] <= metrics["max"]


def test_render_markdown_has_header() -> None:
    out = variance("next-event", n_seeds=2)
    md = render_markdown([out])
    assert "Task" in md
    assert "Mean" in md
    assert "next-event" in md
    assert "top1" in md


def test_run_one_unknown_task_raises() -> None:
    with pytest.raises(ValueError, match="unknown task"):
        _run_one(seed=0, task="not-a-task")


def test_variance_zero_seeds_raises() -> None:
    with pytest.raises(ValueError, match="n_seeds must be >= 1"):
        variance("next-event", n_seeds=0)


def test_main_json_format_structure(capsys) -> None:
    """--format json outputs a JSON array with one entry per task."""
    rc = main(["--n", "1", "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) == len(TASKS)
    for entry in data:
        assert "task" in entry
        assert entry["n_seeds"] == 1
        assert "metrics" in entry


def test_main_json_tasks_filter(capsys) -> None:
    """--tasks restricts the JSON output to the requested subset."""
    rc = main(["--n", "1", "--tasks", "next-event", "outcome", "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert len(data) == 2
    assert {d["task"] for d in data} == {"next-event", "outcome"}


def test_main_markdown_contains_table(capsys) -> None:
    """Default markdown format contains the task table header."""
    rc = main(["--n", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| Task |" in out
    assert "Mean" in out
    assert "## Cross-seed variance" in out


def test_main_single_task_markdown_row_count(capsys) -> None:
    """Single-task run emits exactly one data row in the markdown table."""
    rc = main(["--n", "1", "--tasks", "bottleneck"])
    assert rc == 0
    out = capsys.readouterr().out
    pipe_rows = [line for line in out.splitlines() if line.startswith("|")]
    assert len(pipe_rows) == 3  # header, separator, one data row
