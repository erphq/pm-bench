"""Leaderboard loading + verification.

The on-disk format lives under `leaderboard/<task>/<dataset>.json`.
Reference predictions ship next to the JSON under
`leaderboard/predictions/<task>/<dataset>/<model>.csv[.gz]`. Reading
+ rescoring is pure Python — no torch, no network, deterministic.

Score drift is the only failure mode: the recorded `score` must match
what `pm_bench.score.score_next_event` produces today against the
checked-in predictions and the freshly-extracted prefixes for the
named dataset. If the model code changes the numbers, the leaderboard
file changes alongside it — no exceptions.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pm_bench.predictions import Prediction
from pm_bench.prefixes import PREFIX_SEP, Prefix, extract_prefixes
from pm_bench.score import score_next_event


@dataclass(frozen=True)
class Entry:
    model: str
    version: str
    predictions_path: str
    score: dict
    code: str | None = None
    paper: str | None = None
    scored_at: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class Board:
    task: str
    dataset: str
    metric: str
    entries: list[Entry]
    raw: dict


def load_board(path: str | Path) -> Board:
    """Load a leaderboard JSON file."""
    p = Path(path)
    raw = json.loads(p.read_text())
    entries = [
        Entry(
            model=e["model"],
            version=e["version"],
            predictions_path=e["predictions_path"],
            score=e["score"],
            code=e.get("code"),
            paper=e.get("paper"),
            scored_at=e.get("scored_at"),
            notes=e.get("notes"),
        )
        for e in raw["entries"]
    ]
    return Board(
        task=raw["task"],
        dataset=raw["dataset"],
        metric=raw["metric"],
        entries=entries,
        raw=raw,
    )


def _open_predictions(path: Path) -> Iterable[Prediction]:
    """Yield Prediction rows from a (gzipped or plain) CSV file."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ranked_str = row["predictions"]
            ranked = tuple(ranked_str.split(PREFIX_SEP)) if ranked_str else ()
            yield Prediction(
                case_id=row["case_id"],
                prefix_idx=int(row["prefix_idx"]),
                ranked=ranked,
            )


def _truth_for_dataset(name: str) -> list[Prefix]:
    """Build the canonical truth set for a known dataset.

    Today only `synthetic-toy` is supported — once a real dataset is
    pinned this dispatch grows a branch per dataset, gated on the cached
    file's sha256.
    """
    if name == "synthetic-toy":
        from pm_bench import _synth
        from pm_bench.split import case_chrono_split

        events = list(_synth.synthetic_log())
        s = case_chrono_split(events)
        return list(extract_prefixes(events, s.test))
    raise ValueError(
        f"truth for dataset {name!r} not yet wired; pin a registry hash "
        "and add the dispatch branch"
    )


def rescore(board: Board, repo_root: str | Path = ".") -> list[tuple[Entry, dict]]:
    """Re-run scoring for every entry; return (entry, fresh_score) pairs."""
    if board.task != "next-event":
        raise ValueError(f"rescore only supports next-event today (got {board.task})")
    truth = _truth_for_dataset(board.dataset)
    truth_keys = [(t.case_id, t.prefix_idx) for t in truth]
    truth_next = [t.true_next for t in truth]

    out: list[tuple[Entry, dict]] = []
    for entry in board.entries:
        pred_path = Path(repo_root) / entry.predictions_path
        pred_lookup = {
            (p.case_id, p.prefix_idx): list(p.ranked)
            for p in _open_predictions(pred_path)
        }
        missing = [k for k in truth_keys if k not in pred_lookup]
        if missing:
            raise ValueError(
                f"{entry.model}: predictions missing {len(missing)} target(s); "
                f"first missing {missing[0]}"
            )
        ranked = [pred_lookup[k] for k in truth_keys]
        s = score_next_event(ranked, truth_next)
        out.append(
            (entry, {"top1": s.top1, "top3": s.top3, "n": s.n}),
        )
    return out


def verify(board: Board, repo_root: str | Path = ".", *, tol: float = 1e-9) -> list[str]:
    """Return a list of human-readable drift messages (empty = clean)."""
    drifts: list[str] = []
    for entry, fresh in rescore(board, repo_root=repo_root):
        for k in ("top1", "top3", "n"):
            recorded = entry.score.get(k)
            actual = fresh[k]
            ok = recorded == actual if isinstance(actual, int) else (
                recorded is not None and math.isclose(recorded, actual, abs_tol=tol)
            )
            if not ok:
                drifts.append(
                    f"{entry.model}: {k} drift — recorded={recorded} actual={actual}"
                )
    return drifts


def standings(board: Board, *, key: str = "top1") -> list[Entry]:
    """Return entries sorted by the given score key, descending."""
    return sorted(board.entries, key=lambda e: e.score.get(key, float("-inf")), reverse=True)
