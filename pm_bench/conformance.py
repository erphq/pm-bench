"""Conformance task - DFG submission format and helpers.

The submission for `--task conformance` is a JSON file with the model's
directly-follows graph (DFG):

    {"transitions": [["received", "paid"], ["paid", "shipped"], ...]}

Order doesn't matter; duplicates are ignored. The score is a structural
comparison between the submitted DFG and the DFG observed on the
held-out partition (fitness × precision → F-score).

This is a deliberately simple conformance metric - alignment-based
replay against a Petri net is more principled but needs pm4py. The
DFG version is enough to anchor the leaderboard and rejects models
that ignore the data entirely.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from pm_bench.split import Activity, CaseId, Event


def extract_dfg(
    events: Iterable[Event], case_ids: Iterable[CaseId]
) -> set[tuple[Activity, Activity]]:
    """Return the directly-follows graph for the given case ids.

    For each case, every chronologically-consecutive (a, b) pair is
    added to the set.
    """
    keep = set(case_ids)
    by_case: dict[CaseId, list[tuple[Activity, object]]] = {}
    for case_id, activity, ts in events:
        if case_id not in keep:
            continue
        by_case.setdefault(case_id, []).append((activity, ts))

    out: set[tuple[Activity, Activity]] = set()
    for rows in by_case.values():
        rows.sort(key=lambda r: r[1])
        for (a, _), (b, _) in zip(rows, rows[1:], strict=False):
            out.add((a, b))
    return out


def write_model_json(transitions: Iterable[tuple[Activity, Activity]], path: str | Path) -> int:
    """Write a submission model JSON. Returns the number of transitions."""
    pairs = sorted({tuple(t) for t in transitions})
    Path(path).write_text(json.dumps({"transitions": [list(p) for p in pairs]}, indent=2))
    return len(pairs)


def read_model_json(path: str | Path) -> set[tuple[Activity, Activity]]:
    """Read a submission model JSON into a set of (a, b) pairs.

    Tolerates duplicates and any order. Raises ValueError if the JSON
    is missing the `transitions` key or has a wrong shape.
    """
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict) or "transitions" not in raw:
        raise ValueError(f"{path}: model JSON must have a top-level 'transitions' key")
    pairs = raw["transitions"]
    if not isinstance(pairs, list):
        raise ValueError(f"{path}: 'transitions' must be a list of [a, b] pairs")
    out: set[tuple[Activity, Activity]] = set()
    for i, p in enumerate(pairs):
        if not isinstance(p, list) or len(p) != 2:
            raise ValueError(f"{path}: transitions[{i}] must be a 2-element list")
        out.add((p[0], p[1]))
    return out
