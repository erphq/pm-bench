"""Smoke tests for the cross-seed variance harness."""
from __future__ import annotations

import pytest

from bench.seeds import TASKS, _run_one, render_markdown, variance


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
