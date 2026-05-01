"""CLI for pm-bench."""
from __future__ import annotations

import json
import sys

import click

from pm_bench import _synth
from pm_bench.baselines.markov import fit_markov, predict_markov
from pm_bench.baselines.mean_time import (
    fit_mean_time,
    predict_mean_time,
    read_time_predictions_csv,
    write_time_predictions_csv,
)
from pm_bench.baselines.mean_wait import fit_mean_wait, predict_mean_wait
from pm_bench.baselines.prior_outcome import (
    fit_prior_outcome,
    predict_prior_outcome,
    read_outcome_predictions_csv,
    write_outcome_predictions_csv,
)
from pm_bench.bottleneck import (
    extract_bottleneck_targets,
    read_bottleneck_predictions_csv,
    read_bottleneck_targets_csv,
    write_bottleneck_predictions_csv,
    write_bottleneck_targets_csv,
)
from pm_bench.conformance import extract_dfg, read_model_json, write_model_json
from pm_bench.fetch import (
    FetchError,
    ManualFetchRequired,
    ensure_cached,
    sha256_file,
)
from pm_bench.leaderboard import (
    all_standings_markdown,
    board_to_markdown,
    load_board,
    standings,
    verify,
)
from pm_bench.predictions import read_predictions_csv, write_predictions_csv
from pm_bench.prefixes import (
    extract_outcome_targets,
    extract_prefixes,
    extract_remaining_time_targets,
    read_outcome_targets_csv,
    read_prefixes_csv,
    read_time_targets_csv,
    write_outcome_targets_csv,
    write_prefixes_csv,
    write_time_targets_csv,
)
from pm_bench.registry import get_dataset, load_registry
from pm_bench.score import (
    score_bottleneck,
    score_conformance,
    score_next_event,
    score_outcome,
    score_remaining_time,
)
from pm_bench.split import case_chrono_split


def _load_events(name: str) -> list:
    """Return a materialized event list for a dataset.

    Three supported inputs:
    - `synthetic-toy` → bundled deterministic generator
    - any path that looks like a CSV (`.csv` / `.csv.gz` / contains `/`)
      → loaded via `pm_bench.io.read_csv_log`
    - any other registry name → not yet wired (v0.1 fetch machinery
      handles the cache; XES parsing lands when a dataset is pinned)
    """
    from pm_bench.io import looks_like_path, read_csv_log

    if looks_like_path(name):
        try:
            return read_csv_log(name)
        except FileNotFoundError:
            click.echo(f"no such file: {name}", err=True)
            sys.exit(1)
        except ValueError as exc:
            click.echo(f"{exc}", err=True)
            sys.exit(2)
    if name == "synthetic-toy":
        return list(_synth.synthetic_log())
    click.echo(
        f"unknown dataset: {name}. Use 'synthetic-toy', a CSV path, or wait "
        "for the v0.1 fetch machinery to wire your registry entry.",
        err=True,
    )
    sys.exit(1)


def _outcome_rule(name: str):
    """Return the per-dataset positive-outcome predicate."""
    if name == "synthetic-toy":
        return _synth.is_positive_outcome
    raise click.UsageError(
        f"outcome rule for {name!r} not yet defined; pin a dataset hash and "
        "register its outcome rule"
    )


@click.group()
@click.version_option()
def main() -> None:
    """pm-bench - the open process-mining benchmark."""


@main.command(name="list")
def cmd_list() -> None:
    """List datasets in the registry."""
    for d in load_registry():
        ready = "bundled" if d.bundled else ("ready" if d.download_url else "manual fetch")
        click.echo(f"{d.name:18s} {d.cases:>8} cases {d.events:>11} events  [{ready}]")


@main.command()
@click.argument("name")
def info(name: str) -> None:
    """Show details for a dataset."""
    try:
        d = get_dataset(name)
    except KeyError:
        click.echo(f"unknown dataset: {name}", err=True)
        sys.exit(1)
    click.echo(
        json.dumps(
            {
                "name": d.name,
                "title": d.title,
                "cases": d.cases,
                "events": d.events,
                "license": d.license,
                "format": d.format,
                "landing_url": d.landing_url,
                "download_url": d.download_url,
                "bundled": d.bundled,
            },
            indent=2,
        ),
    )


@main.command()
@click.argument("name")
@click.option(
    "--pin",
    is_flag=True,
    default=False,
    help="After locating the cached file, print a registry.yml patch with its sha256.",
)
def fetch(name: str, pin: bool) -> None:
    """Make a dataset available locally and verify its hash.

    Auto-downloads when `download_url` is set; otherwise prints
    instructions for the manual TOS-gated download path (4TU / Mendeley).
    """
    try:
        d = get_dataset(name)
    except KeyError:
        click.echo(f"unknown dataset: {name}", err=True)
        sys.exit(1)

    if d.format == "synthetic":
        click.echo(f"{name}: generated on demand, no fetch needed")
        return

    try:
        result = ensure_cached(d)
    except ManualFetchRequired as exc:
        # Special-cased only so we can also handle --pin against a file the
        # user just placed by hand. If the file is now there, recurse via
        # ensure_cached; otherwise print the instructions and bail.
        path = exc.expected_path
        if path.exists():
            actual = sha256_file(path)
            click.echo(f"{name}: cached at {path}")
            click.echo(f"  sha256: {actual}")
            if pin:
                _print_pin_patch(name, actual)
            elif d.sha256 is None:
                click.echo("  (registry hash unset - re-run with --pin to emit a patch)")
            return
        click.echo(str(exc), err=True)
        sys.exit(2)
    except FetchError as exc:
        click.echo(f"{name}: {exc}", err=True)
        sys.exit(2)

    state = "downloaded" if result.downloaded else "cached"
    pinned = "verified" if result.pinned else "unpinned"
    click.echo(f"{name}: {state} at {result.path} ({pinned})")
    click.echo(f"  sha256: {result.sha256}")
    if pin and not result.pinned:
        _print_pin_patch(name, result.sha256)


def _print_pin_patch(name: str, digest: str) -> None:
    """Print a YAML snippet the user can paste into registry.yml."""
    click.echo("")
    click.echo("# paste under the matching dataset entry in pm_bench/registry.yml:")
    click.echo(f"  - name: {name}")
    click.echo(f"    sha256: {digest}")


@main.command()
@click.argument("name")
@click.option("--task", default="next-event", show_default=True)
def split(name: str, task: str) -> None:
    """Produce a train/val/test split for a dataset.

    v0 supports `synthetic-toy` only; other datasets require manual fetch.
    """
    events = _load_events(name)
    s = case_chrono_split(events)
    click.echo(
        json.dumps(
            {
                "task": task,
                "dataset": name,
                "sizes": {"train": len(s.train), "val": len(s.val), "test": len(s.test)},
                "train": s.train,
                "val": s.val,
                "test": s.test,
            },
            indent=2,
        ),
    )


@main.command()
@click.argument("name")
@click.option(
    "--split",
    "split_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to a split.json emitted by `pm-bench split`.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False),
    required=True,
    help="Where to write the prefixes CSV.",
)
@click.option(
    "--partition",
    type=click.Choice(["test", "val", "train"]),
    default="test",
    show_default=True,
    help="Which split partition to emit prefixes for. The leaderboard scores 'test'.",
)
@click.option(
    "--task",
    type=click.Choice(
        ["next-event", "remaining-time", "outcome", "bottleneck", "conformance"]
    ),
    default="next-event",
    show_default=True,
)
def prefixes(name: str, split_path: str, out_path: str, partition: str, task: str) -> None:
    """Emit prediction targets for a partition.

    For `next-event`: rows are `(case_id, prefix_idx, prefix, true_next)`.
    For `remaining-time`: rows are `(case_id, prefix_idx, remaining_days)`.
    The (case_id, prefix_idx) keys join across the two truth files.
    """
    events = _load_events(name)
    with open(split_path) as f:
        split_data = json.load(f)
    case_ids = split_data[partition]
    if task == "next-event":
        n = write_prefixes_csv(extract_prefixes(events, case_ids), out_path)
    elif task == "remaining-time":
        n = write_time_targets_csv(
            extract_remaining_time_targets(events, case_ids), out_path
        )
    elif task == "outcome":
        rule = _outcome_rule(name)
        n = write_outcome_targets_csv(
            extract_outcome_targets(events, case_ids, rule), out_path
        )
    else:
        # bottleneck
        n = write_bottleneck_targets_csv(
            extract_bottleneck_targets(events, case_ids), out_path
        )
    click.echo(f"wrote {n} prefixes to {out_path} (task={task} partition={partition})")


@main.command()
@click.argument("name")
@click.option(
    "--split",
    "split_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
)
@click.option(
    "--prefixes",
    "prefixes_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Truth file emitted by `pm-bench prefixes`.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False),
    required=True,
)
@click.option(
    "--baseline",
    type=click.Choice(["markov", "mean", "prior", "mean-wait"]),
    default="markov",
    show_default=True,
    help=(
        "markov → next-event; mean → remaining-time; "
        "prior → outcome; mean-wait → bottleneck."
    ),
)
@click.option(
    "--task",
    type=click.Choice(
        ["next-event", "remaining-time", "outcome", "bottleneck", "conformance"]
    ),
    default="next-event",
    show_default=True,
)
def predict(
    name: str,
    split_path: str,
    prefixes_path: str,
    out_path: str,
    baseline: str,
    task: str,
) -> None:
    """Run a reference baseline and emit predictions.csv."""
    events = _load_events(name)
    with open(split_path) as f:
        split_data = json.load(f)

    if task == "next-event":
        if baseline != "markov":
            raise click.UsageError(f"baseline {baseline!r} doesn't apply to next-event")
        model = fit_markov(events, split_data["train"])
        targets = read_prefixes_csv(prefixes_path)
        preds = predict_markov(model, targets)
        n = write_predictions_csv(preds, out_path)
    elif task == "remaining-time":
        if baseline != "mean":
            raise click.UsageError(f"baseline {baseline!r} doesn't apply to remaining-time")
        time_model = fit_mean_time(events, split_data["train"])
        time_targets = read_time_targets_csv(prefixes_path)
        time_preds = predict_mean_time(time_model, time_targets)
        n = write_time_predictions_csv(time_preds, out_path)
    elif task == "outcome":
        if baseline != "prior":
            raise click.UsageError(f"baseline {baseline!r} doesn't apply to outcome")
        rule = _outcome_rule(name)
        outcome_model = fit_prior_outcome(events, split_data["train"], rule)
        outcome_targets = read_outcome_targets_csv(prefixes_path)
        # Build full activity sequences keyed by case_id so the baseline
        # can read off each prefix's last activity.
        seq_by_case: dict[str, list[str]] = {}
        for cid, act, _ts in sorted(events, key=lambda e: e[2]):
            seq_by_case.setdefault(cid, []).append(act)
        outcome_preds = predict_prior_outcome(outcome_model, outcome_targets, seq_by_case)
        n = write_outcome_predictions_csv(outcome_preds, out_path)
    else:
        # bottleneck
        if baseline != "mean-wait":
            raise click.UsageError(f"baseline {baseline!r} doesn't apply to bottleneck")
        wait_model = fit_mean_wait(events, split_data["train"])
        wait_targets = read_bottleneck_targets_csv(prefixes_path)
        wait_preds = predict_mean_wait(wait_model, wait_targets)
        n = write_bottleneck_predictions_csv(wait_preds, out_path)
    click.echo(f"wrote {n} predictions to {out_path} (task={task} baseline={baseline})")


@main.command()
@click.argument("name")
@click.option(
    "--split",
    "split_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False),
    required=True,
    help="Where to write the discovered-model JSON.",
)
@click.option(
    "--baseline",
    type=click.Choice(["dfg"]),
    default="dfg",
    show_default=True,
    help="dfg → directly-follows graph from training cases.",
)
def discover(name: str, split_path: str, out_path: str, baseline: str) -> None:
    """Discover a process model from training cases.

    The submission for the conformance task is a model JSON. Today only
    the DFG baseline ships in-tree - other discoverers (alpha, inductive)
    can be added behind a `[discovery]` extra without changing the
    submission format.
    """
    events = _load_events(name)
    with open(split_path) as f:
        split_data = json.load(f)
    if baseline != "dfg":
        raise click.UsageError(f"unknown discoverer: {baseline}")
    dfg = extract_dfg(events, split_data["train"])
    n = write_model_json(dfg, out_path)
    click.echo(f"wrote model with {n} transitions to {out_path} (baseline={baseline})")


@main.command()
@click.argument("predictions_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--prefixes",
    "prefixes_path",
    type=click.Path(exists=True, dir_okay=False),
    required=False,
    help="Truth file from `pm-bench prefixes` (required for non-conformance tasks).",
)
@click.option(
    "--dataset",
    "dataset_name",
    required=False,
    help="Dataset name (required for --task conformance - used to extract test DFG).",
)
@click.option(
    "--split",
    "split_path",
    type=click.Path(exists=True, dir_okay=False),
    required=False,
    help="Split JSON (required for --task conformance - used to identify test cases).",
)
@click.option(
    "--task",
    type=click.Choice(
        ["next-event", "remaining-time", "outcome", "bottleneck", "conformance"]
    ),
    default="next-event",
    show_default=True,
)
def score(
    predictions_path: str,
    prefixes_path: str | None,
    dataset_name: str | None,
    split_path: str | None,
    task: str,
) -> None:
    """Score predictions against the truth file (or, for conformance, against
    the test-partition DFG of a named dataset)."""
    if task == "conformance":
        if not dataset_name or not split_path:
            click.echo(
                "conformance scoring needs --dataset and --split (the model is "
                "judged against the test partition's directly-follows graph)",
                err=True,
            )
            sys.exit(1)
        events = _load_events(dataset_name)
        with open(split_path) as f:
            split_data = json.load(f)
        truth_dfg = extract_dfg(events, split_data["test"])
        try:
            model_dfg = read_model_json(predictions_path)
        except ValueError as exc:
            click.echo(str(exc), err=True)
            sys.exit(2)
        cs = score_conformance(model_dfg, truth_dfg)
        click.echo(
            json.dumps(
                {
                    "task": task,
                    "fitness": cs.fitness,
                    "precision": cs.precision,
                    "fscore": cs.fscore,
                    "n_test_transitions": cs.n_test_transitions,
                    "n_model_transitions": cs.n_model_transitions,
                },
                indent=2,
            ),
        )
        return

    if not prefixes_path:
        click.echo(f"--prefixes is required for --task {task}", err=True)
        sys.exit(1)

    if task == "next-event":
        truth_rows = read_prefixes_csv(prefixes_path)
        pred_rows = read_predictions_csv(predictions_path)
        pred_lookup = {(p.case_id, p.prefix_idx): p.ranked for p in pred_rows}
        missing = [
            (t.case_id, t.prefix_idx)
            for t in truth_rows
            if (t.case_id, t.prefix_idx) not in pred_lookup
        ]
        if missing:
            click.echo(
                f"predictions.csv is missing {len(missing)} target(s); "
                f"first: {missing[0]}",
                err=True,
            )
            sys.exit(2)
        ranked = [list(pred_lookup[(t.case_id, t.prefix_idx)]) for t in truth_rows]
        truth = [t.true_next for t in truth_rows]
        s = score_next_event(ranked, truth)
        click.echo(
            json.dumps(
                {"task": task, "top1": s.top1, "top3": s.top3, "n": s.n},
                indent=2,
            ),
        )
        return

    if task == "remaining-time":
        truth_time = read_time_targets_csv(prefixes_path)
        pred_time = read_time_predictions_csv(predictions_path)
        pred_t_lookup = {(p.case_id, p.prefix_idx): p.predicted_days for p in pred_time}
        missing = [
            (t.case_id, t.prefix_idx)
            for t in truth_time
            if (t.case_id, t.prefix_idx) not in pred_t_lookup
        ]
        if missing:
            click.echo(
                f"predictions is missing {len(missing)} target(s); first: {missing[0]}",
                err=True,
            )
            sys.exit(2)
        preds_floats = [pred_t_lookup[(t.case_id, t.prefix_idx)] for t in truth_time]
        truth_floats = [t.remaining_days for t in truth_time]
        rt = score_remaining_time(preds_floats, truth_floats)
        click.echo(
            json.dumps(
                {"task": task, "mae_days": rt.mae_days, "n": rt.n},
                indent=2,
            ),
        )
        return

    if task == "outcome":
        truth_o = read_outcome_targets_csv(prefixes_path)
        pred_o = read_outcome_predictions_csv(predictions_path)
        pred_o_lookup = {(p.case_id, p.prefix_idx): p.score for p in pred_o}
        missing = [
            (t.case_id, t.prefix_idx)
            for t in truth_o
            if (t.case_id, t.prefix_idx) not in pred_o_lookup
        ]
        if missing:
            click.echo(
                f"predictions is missing {len(missing)} target(s); first: {missing[0]}",
                err=True,
            )
            sys.exit(2)
        preds_o = [pred_o_lookup[(t.case_id, t.prefix_idx)] for t in truth_o]
        truth_o_int = [t.outcome for t in truth_o]
        os_ = score_outcome(preds_o, truth_o_int)
        click.echo(
            json.dumps(
                {"task": task, "auc": os_.auc, "n": os_.n, "n_pos": os_.n_pos},
                indent=2,
            ),
        )
        return

    # bottleneck
    truth_b = read_bottleneck_targets_csv(prefixes_path)
    pred_b = read_bottleneck_predictions_csv(predictions_path)
    truth_dict = {(t.activity_a, t.activity_b): t.mean_wait_seconds for t in truth_b}
    pred_dict = {(p.activity_a, p.activity_b): p.predicted_wait_seconds for p in pred_b}
    bs = score_bottleneck(pred_dict, truth_dict, k=10)
    click.echo(
        json.dumps(
            {
                "task": task,
                "ndcg_at_k": bs.ndcg_at_k,
                "k": bs.k,
                "n_transitions": bs.n_transitions,
            },
            indent=2,
        ),
    )


@main.command()
@click.argument("task", required=False)
@click.argument("dataset", required=False)
@click.option(
    "--verify",
    "do_verify",
    is_flag=True,
    default=False,
    help="Re-score every entry and fail if recorded scores have drifted.",
)
@click.option(
    "--all",
    "do_all",
    is_flag=True,
    default=False,
    help="Walk every leaderboard/<task>/<dataset>.json and verify each.",
)
@click.option(
    "--markdown",
    "do_markdown",
    is_flag=True,
    default=False,
    help="Emit a markdown rendering. With --all, prints the full STANDINGS doc.",
)
@click.option(
    "--repo-root",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="Repo root that `predictions_path` entries are relative to.",
)
def leaderboard(
    task: str | None,
    dataset: str | None,
    do_verify: bool,
    do_all: bool,
    do_markdown: bool,
    repo_root: str,
) -> None:
    """Print standings for a (task, dataset) pair, optionally rescoring.

    With `--all`, walks every standings file under `leaderboard/` -
    the lever CI pulls to verify the full repo in one go.
    """
    if do_all:
        if do_markdown:
            click.echo(all_standings_markdown(repo_root=repo_root), nl=False)
            return
        from pathlib import Path

        root = Path(repo_root) / "leaderboard"
        files = sorted(root.glob("*/*.json"))
        if not files:
            click.echo(f"no leaderboard files under {root}", err=True)
            sys.exit(1)
        any_drift = False
        for f in files:
            try:
                board = load_board(f)
            except (KeyError, ValueError) as exc:
                click.echo(f"{f.relative_to(repo_root)}: malformed - {exc}", err=True)
                any_drift = True
                continue
            drifts = verify(board, repo_root=repo_root) if do_verify else []
            tag = "OK" if not drifts else f"DRIFT ({len(drifts)})"
            click.echo(f"{board.task}/{board.dataset}: {tag} - {len(board.entries)} entry(ies)")
            for d in drifts:
                click.echo(f"  {d}", err=True)
                any_drift = True
        sys.exit(2 if any_drift else 0)

    if not task or not dataset:
        click.echo("usage: pm-bench leaderboard <task> <dataset> [--verify]  OR  --all", err=True)
        sys.exit(1)

    path = f"leaderboard/{task}/{dataset}.json"
    full = f"{repo_root.rstrip('/')}/{path}"
    try:
        board = load_board(full)
    except FileNotFoundError:
        click.echo(f"no leaderboard at {path}", err=True)
        sys.exit(1)

    if do_verify:
        drifts = verify(board, repo_root=repo_root)
        if drifts:
            for d in drifts:
                click.echo(d, err=True)
            sys.exit(2)
        click.echo(f"verified {len(board.entries)} entr(ies) - no drift")

    if do_markdown:
        click.echo(board_to_markdown(board))
        return

    width = max((len(e.model) for e in board.entries), default=10)
    click.echo(f"{board.task} · {board.dataset} · {board.metric}")
    click.echo("-" * (width + 30))
    for e in standings(board):
        if board.task == "remaining-time":
            mae = e.score.get("mae_days")
            n = e.score.get("n")
            click.echo(f"{e.model:<{width}}  mae_days={mae:.4f}  n={n}")
        elif board.task == "outcome":
            auc = e.score.get("auc")
            n = e.score.get("n")
            n_pos = e.score.get("n_pos")
            click.echo(f"{e.model:<{width}}  auc={auc:.4f}  n={n}  n_pos={n_pos}")
        elif board.task == "bottleneck":
            ndcg = e.score.get("ndcg_at_k")
            k = e.score.get("k")
            n_t = e.score.get("n_transitions")
            click.echo(f"{e.model:<{width}}  ndcg@{k}={ndcg:.4f}  n_transitions={n_t}")
        elif board.task == "conformance":
            f_ = e.score.get("fscore")
            fit = e.score.get("fitness")
            pr = e.score.get("precision")
            click.echo(
                f"{e.model:<{width}}  F={f_:.4f}  fitness={fit:.4f}  precision={pr:.4f}"
            )
        else:
            top1 = e.score.get("top1")
            top3 = e.score.get("top3")
            n = e.score.get("n")
            click.echo(
                f"{e.model:<{width}}  top1={top1:.4f}  top3={top3:.4f}  n={n}"
            )


if __name__ == "__main__":
    main()
