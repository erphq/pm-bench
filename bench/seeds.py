"""Cross-seed variance harness for the reference baselines on synthetic-toy.

Runs the full pipeline (split → prefixes → predict → score) at N seeds
of the synthetic generator, reporting mean / std / min / max per task.
Helps answer "how much does baseline performance jitter across data
draws?" — the variance band a real submission has to clear before its
gain is statistically interesting.

Run as a script:

    python -m bench.seeds            # default 10 seeds
    python -m bench.seeds --n 30     # more samples → tighter CIs

The output is a markdown table, suitable for paste into a PR description.
"""
from __future__ import annotations

import argparse
import statistics

from pm_bench import _synth
from pm_bench.baselines.markov import fit_markov, predict_markov
from pm_bench.baselines.mean_time import fit_mean_time, predict_mean_time
from pm_bench.baselines.mean_wait import fit_mean_wait, predict_mean_wait
from pm_bench.baselines.prior_outcome import fit_prior_outcome, predict_prior_outcome
from pm_bench.bottleneck import extract_bottleneck_targets
from pm_bench.conformance import extract_dfg
from pm_bench.prefixes import (
    extract_outcome_targets,
    extract_prefixes,
    extract_remaining_time_targets,
)
from pm_bench.score import (
    score_bottleneck,
    score_conformance,
    score_next_event,
    score_outcome,
    score_remaining_time,
)
from pm_bench.split import case_chrono_split


def _run_one(seed: int, task: str) -> dict:
    """Run one seed end-to-end for a task; return the headline metric."""
    events = list(_synth.synthetic_log(seed=seed))
    s = case_chrono_split(events)

    if task == "next-event":
        model = fit_markov(events, s.train)
        targets = list(extract_prefixes(events, s.test))
        preds = predict_markov(model, targets)
        ranked = [list(p.ranked) for p in preds]
        truth = [t.true_next for t in targets]
        return {"top1": score_next_event(ranked, truth).top1}

    if task == "remaining-time":
        model = fit_mean_time(events, s.train)
        targets = list(extract_remaining_time_targets(events, s.test))
        preds = predict_mean_time(model, targets)
        return {
            "mae_days": score_remaining_time(
                [p.predicted_days for p in preds],
                [t.remaining_days for t in targets],
            ).mae_days
        }

    if task == "outcome":
        rule = _synth.is_positive_outcome
        model = fit_prior_outcome(events, s.train, rule)
        targets = list(extract_outcome_targets(events, s.test, rule))
        seq_by_case: dict[str, list[str]] = {}
        for cid, act, _ts in sorted(events, key=lambda e: e[2]):
            seq_by_case.setdefault(cid, []).append(act)
        preds = predict_prior_outcome(model, targets, seq_by_case)
        return {
            "auc": score_outcome(
                [p.score for p in preds],
                [t.outcome for t in targets],
            ).auc
        }

    if task == "bottleneck":
        model = fit_mean_wait(events, s.train)
        targets = list(extract_bottleneck_targets(events, s.test))
        preds = predict_mean_wait(model, targets)
        truth_dict = {(t.activity_a, t.activity_b): t.mean_wait_seconds for t in targets}
        pred_dict = {(p.activity_a, p.activity_b): p.predicted_wait_seconds for p in preds}
        return {"ndcg_at_k": score_bottleneck(pred_dict, truth_dict).ndcg_at_k}

    if task == "conformance":
        model_dfg = extract_dfg(events, s.train)
        truth_dfg = extract_dfg(events, s.test)
        return {"fscore": score_conformance(model_dfg, truth_dfg).fscore}

    raise ValueError(f"unknown task: {task}")


def variance(task: str, n_seeds: int) -> dict:
    """Return mean / std / min / max across seeds for a task's headline metric."""
    if n_seeds < 1:
        raise ValueError(f"n_seeds must be >= 1, got {n_seeds}")
    runs = [_run_one(seed, task) for seed in range(n_seeds)]
    metric_keys = list(runs[0].keys())
    out: dict = {"task": task, "n_seeds": n_seeds, "metrics": {}}
    for k in metric_keys:
        values = [r[k] for r in runs]
        out["metrics"][k] = {
            "mean": statistics.fmean(values),
            "std": statistics.pstdev(values) if n_seeds > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }
    return out


TASKS: list[str] = ["next-event", "remaining-time", "outcome", "bottleneck", "conformance"]


def render_markdown(results: list[dict]) -> str:
    """Pretty-print a list of variance dicts as a markdown table."""
    lines = [
        "| Task | Metric | Mean | Std | Min | Max |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in results:
        for metric, stats in r["metrics"].items():
            lines.append(
                f"| {r['task']} | {metric} | {stats['mean']:.4f} | "
                f"{stats['std']:.4f} | {stats['min']:.4f} | {stats['max']:.4f} |"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", "--n-seeds", dest="n_seeds", type=int, default=10)
    p.add_argument("--tasks", nargs="*", default=TASKS, choices=TASKS)
    p.add_argument(
        "--format", choices=["markdown", "json"], default="markdown",
    )
    args = p.parse_args(argv)

    results = [variance(task, args.n_seeds) for task in args.tasks]

    if args.format == "json":
        import json

        print(json.dumps(results, indent=2))
    else:
        print(f"## Cross-seed variance on synthetic-toy (n={args.n_seeds})\n")
        print(render_markdown(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
