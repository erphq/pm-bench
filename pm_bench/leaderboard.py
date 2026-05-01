"""Leaderboard loading + verification.

The on-disk format lives under `leaderboard/<task>/<dataset>.json`.
Reference predictions ship next to the JSON under
`leaderboard/predictions/<task>/<dataset>/<model>.csv[.gz]`. Reading
+ rescoring is pure Python - no torch, no network, deterministic.

Score drift is the only failure mode: the recorded `score` must match
what `pm_bench.score.score_next_event` produces today against the
checked-in predictions and the freshly-extracted prefixes for the
named dataset. If the model code changes the numbers, the leaderboard
file changes alongside it - no exceptions.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pm_bench.bottleneck import BottleneckTarget, extract_bottleneck_targets
from pm_bench.conformance import extract_dfg, read_model_json
from pm_bench.predictions import Prediction
from pm_bench.prefixes import (
    PREFIX_SEP,
    Prefix,
    TimeTarget,
    extract_prefixes,
    extract_remaining_time_targets,
)
from pm_bench.score import (
    score_bottleneck,
    score_conformance,
    score_next_event,
    score_remaining_time,
)


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


def _events_and_test_cases(name: str):
    """Return (events, test_case_ids) for a known dataset.

    Today only `synthetic-toy` is supported - once a real dataset is
    pinned this dispatch grows a branch per dataset, gated on the cached
    file's sha256.
    """
    if name == "synthetic-toy":
        from pm_bench import _synth
        from pm_bench.split import case_chrono_split

        events = list(_synth.synthetic_log())
        s = case_chrono_split(events)
        return events, s.test
    raise ValueError(
        f"truth for dataset {name!r} not yet wired; pin a registry hash "
        "and add the dispatch branch"
    )


def _truth_for_dataset(name: str) -> list[Prefix]:
    """Canonical next-event truth set for a known dataset."""
    events, test_cases = _events_and_test_cases(name)
    return list(extract_prefixes(events, test_cases))


def _time_truth_for_dataset(name: str) -> list[TimeTarget]:
    """Canonical remaining-time truth set for a known dataset."""
    events, test_cases = _events_and_test_cases(name)
    return list(extract_remaining_time_targets(events, test_cases))


def _bottleneck_truth_for_dataset(name: str) -> list[BottleneckTarget]:
    """Canonical bottleneck truth set for a known dataset."""
    events, test_cases = _events_and_test_cases(name)
    return list(extract_bottleneck_targets(events, test_cases))


def _rescore_next_event(board: Board, repo_root: Path) -> list[tuple[Entry, dict]]:
    truth = _truth_for_dataset(board.dataset)
    truth_keys = [(t.case_id, t.prefix_idx) for t in truth]
    truth_next = [t.true_next for t in truth]

    out: list[tuple[Entry, dict]] = []
    for entry in board.entries:
        pred_path = repo_root / entry.predictions_path
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
        out.append((entry, {"top1": s.top1, "top3": s.top3, "n": s.n}))
    return out


def _rescore_remaining_time(board: Board, repo_root: Path) -> list[tuple[Entry, dict]]:
    import csv
    import gzip

    truth = _time_truth_for_dataset(board.dataset)
    truth_keys = [(t.case_id, t.prefix_idx) for t in truth]
    truth_floats = [t.remaining_days for t in truth]

    out: list[tuple[Entry, dict]] = []
    for entry in board.entries:
        pred_path = repo_root / entry.predictions_path
        opener = gzip.open if str(pred_path).endswith(".gz") else open
        pred_lookup: dict[tuple[str, int], float] = {}
        with opener(pred_path, "rt", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pred_lookup[(row["case_id"], int(row["prefix_idx"]))] = float(row["predicted_days"])
        missing = [k for k in truth_keys if k not in pred_lookup]
        if missing:
            raise ValueError(
                f"{entry.model}: predictions missing {len(missing)} target(s); "
                f"first missing {missing[0]}"
            )
        preds = [pred_lookup[k] for k in truth_keys]
        s = score_remaining_time(preds, truth_floats)
        out.append((entry, {"mae_days": s.mae_days, "n": s.n}))
    return out


def _rescore_bottleneck(board: Board, repo_root: Path) -> list[tuple[Entry, dict]]:
    import csv
    import gzip

    truth = _bottleneck_truth_for_dataset(board.dataset)
    truth_dict = {(t.activity_a, t.activity_b): t.mean_wait_seconds for t in truth}

    out: list[tuple[Entry, dict]] = []
    for entry in board.entries:
        pred_path = repo_root / entry.predictions_path
        opener = gzip.open if str(pred_path).endswith(".gz") else open
        pred_dict: dict[tuple[str, str], float] = {}
        with opener(pred_path, "rt", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pred_dict[(row["activity_a"], row["activity_b"])] = float(
                    row["predicted_wait_seconds"]
                )
        s = score_bottleneck(pred_dict, truth_dict, k=10)
        out.append(
            (
                entry,
                {"ndcg_at_k": s.ndcg_at_k, "k": s.k, "n_transitions": s.n_transitions},
            )
        )
    return out


def _rescore_conformance(board: Board, repo_root: Path) -> list[tuple[Entry, dict]]:
    events, test_cases = _events_and_test_cases(board.dataset)
    truth_dfg = extract_dfg(events, test_cases)

    out: list[tuple[Entry, dict]] = []
    for entry in board.entries:
        model_path = repo_root / entry.predictions_path
        model_dfg = read_model_json(model_path)
        s = score_conformance(model_dfg, truth_dfg)
        out.append(
            (
                entry,
                {
                    "fitness": s.fitness,
                    "precision": s.precision,
                    "fscore": s.fscore,
                    "n_test_transitions": s.n_test_transitions,
                    "n_model_transitions": s.n_model_transitions,
                },
            )
        )
    return out


def rescore(board: Board, repo_root: str | Path = ".") -> list[tuple[Entry, dict]]:
    """Re-run scoring for every entry; return (entry, fresh_score) pairs."""
    root = Path(repo_root)
    if board.task == "next-event":
        return _rescore_next_event(board, root)
    if board.task == "remaining-time":
        return _rescore_remaining_time(board, root)
    if board.task == "bottleneck":
        return _rescore_bottleneck(board, root)
    if board.task == "conformance":
        return _rescore_conformance(board, root)
    raise ValueError(f"unknown task: {board.task}")


def verify(board: Board, repo_root: str | Path = ".", *, tol: float = 1e-9) -> list[str]:
    """Return a list of human-readable drift messages (empty = clean)."""
    drifts: list[str] = []
    for entry, fresh in rescore(board, repo_root=repo_root):
        for k, actual in fresh.items():
            recorded = entry.score.get(k)
            ok = recorded == actual if isinstance(actual, int) else (
                recorded is not None and math.isclose(recorded, actual, abs_tol=tol)
            )
            if not ok:
                drifts.append(
                    f"{entry.model}: {k} drift - recorded={recorded} actual={actual}"
                )
    return drifts


def board_to_markdown(board: Board) -> str:
    """Render a single board as a fenced markdown table.

    Columns are task-aware (top1/top3 for next-event, mae_days for
    remaining-time, auc/n_pos for outcome, ndcg@k for bottleneck).
    """
    rows = standings(board)
    lines = [
        f"### {board.task} · {board.dataset}",
        f"_{board.metric}_",
        "",
    ]
    if board.task == "remaining-time":
        lines.append("| Model | mae_days | n |")
        lines.append("|---|---:|---:|")
        for e in rows:
            mae = e.score.get("mae_days", float("nan"))
            lines.append(f"| `{e.model}` | {mae:.4f} | {e.score.get('n')} |")
    elif board.task == "outcome":
        lines.append("| Model | AUC | n | n_pos |")
        lines.append("|---|---:|---:|---:|")
        for e in rows:
            auc = e.score.get("auc", float("nan"))
            lines.append(
                f"| `{e.model}` | {auc:.4f} | {e.score.get('n')} | {e.score.get('n_pos')} |"
            )
    elif board.task == "bottleneck":
        lines.append("| Model | NDCG@k | k | n_transitions |")
        lines.append("|---|---:|---:|---:|")
        for e in rows:
            ndcg = e.score.get("ndcg_at_k", float("nan"))
            lines.append(
                f"| `{e.model}` | {ndcg:.4f} | {e.score.get('k')} | "
                f"{e.score.get('n_transitions')} |"
            )
    elif board.task == "conformance":
        lines.append("| Model | F | Fitness | Precision | n_test | n_model |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for e in rows:
            f_ = e.score.get("fscore", float("nan"))
            fit = e.score.get("fitness", float("nan"))
            pr = e.score.get("precision", float("nan"))
            lines.append(
                f"| `{e.model}` | {f_:.4f} | {fit:.4f} | {pr:.4f} | "
                f"{e.score.get('n_test_transitions')} | "
                f"{e.score.get('n_model_transitions')} |"
            )
    else:
        # next-event
        lines.append("| Model | top1 | top3 | n |")
        lines.append("|---|---:|---:|---:|")
        for e in rows:
            top1 = e.score.get("top1", float("nan"))
            top3 = e.score.get("top3", float("nan"))
            lines.append(
                f"| `{e.model}` | {top1:.4f} | {top3:.4f} | {e.score.get('n')} |"
            )
    return "\n".join(lines)


def all_standings_markdown(repo_root: str | Path = ".") -> str:
    """Render every leaderboard/<task>/<dataset>.json as one markdown doc."""
    root = Path(repo_root) / "leaderboard"
    files = sorted(root.glob("*/*.json"))
    chunks = [
        "# Standings",
        "",
        "_Auto-generated from `leaderboard/<task>/<dataset>.json` -"
        " regenerate with `pm-bench leaderboard --all --markdown > STANDINGS.md`._",
        "",
    ]
    for f in files:
        board = load_board(f)
        chunks.append(board_to_markdown(board))
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def standings(board: Board, *, key: str | None = None) -> list[Entry]:
    """Return entries sorted by the appropriate score key.

    Direction follows the metric: top1 (higher better) for next-event,
    mae_days (lower better) for remaining-time, auc / ndcg_at_k (higher
    better) for outcome / bottleneck. Pass `key` explicitly to override.
    """
    if key is None:
        if board.task == "remaining-time":
            return sorted(
                board.entries,
                key=lambda e: e.score.get("mae_days", float("inf")),
            )
        if board.task == "outcome":
            key = "auc"
        elif board.task == "bottleneck":
            key = "ndcg_at_k"
        elif board.task == "conformance":
            key = "fscore"
        else:
            key = "top1"
    return sorted(board.entries, key=lambda e: e.score.get(key, float("-inf")), reverse=True)
