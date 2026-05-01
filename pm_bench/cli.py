"""CLI for pm-bench."""
from __future__ import annotations

import json
import sys

import click

from pm_bench import _synth
from pm_bench.baselines.markov import fit_markov, predict_markov
from pm_bench.fetch import (
    FetchError,
    ManualFetchRequired,
    ensure_cached,
    sha256_file,
)
from pm_bench.predictions import read_predictions_csv, write_predictions_csv
from pm_bench.prefixes import extract_prefixes, read_prefixes_csv, write_prefixes_csv
from pm_bench.registry import get_dataset, load_registry
from pm_bench.score import score_next_event
from pm_bench.split import case_chrono_split


def _load_events(name: str) -> list:
    """Return a materialized event list for a dataset.

    v0 supports `synthetic-toy` only; other datasets exit with a clear
    instruction to wait for v0.1's fetch+cache machinery.
    """
    if name != "synthetic-toy":
        click.echo(
            f"v0 only supports 'synthetic-toy' (got {name}); see README for the v0.1 milestone",
            err=True,
        )
        sys.exit(1)
    return list(_synth.synthetic_log())


@click.group()
@click.version_option()
def main() -> None:
    """pm-bench — the open process-mining benchmark."""


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
                click.echo("  (registry hash unset — re-run with --pin to emit a patch)")
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
def prefixes(name: str, split_path: str, out_path: str, partition: str) -> None:
    """Emit prediction targets (prefix → true-next) for a partition.

    The output is the truth file scoring runs against. Submissions
    write a predictions.csv with the same `(case_id, prefix_idx)` keys.
    """
    events = _load_events(name)
    with open(split_path) as f:
        split_data = json.load(f)
    case_ids = split_data[partition]
    n = write_prefixes_csv(extract_prefixes(events, case_ids), out_path)
    click.echo(f"wrote {n} prefixes to {out_path} (partition={partition})")


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
    type=click.Choice(["markov"]),
    default="markov",
    show_default=True,
)
def predict(
    name: str,
    split_path: str,
    prefixes_path: str,
    out_path: str,
    baseline: str,
) -> None:
    """Run a reference baseline and emit predictions.csv."""
    events = _load_events(name)
    with open(split_path) as f:
        split_data = json.load(f)
    if baseline != "markov":
        # click already restricts the choice; this is a guard for the future.
        raise click.UsageError(f"unknown baseline: {baseline}")
    model = fit_markov(events, split_data["train"])
    targets = read_prefixes_csv(prefixes_path)
    preds = predict_markov(model, targets)
    n = write_predictions_csv(preds, out_path)
    click.echo(f"wrote {n} predictions to {out_path} (baseline={baseline})")


@main.command()
@click.argument("predictions_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--prefixes",
    "prefixes_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Truth file from `pm-bench prefixes`.",
)
@click.option("--task", default="next-event", show_default=True)
def score(predictions_path: str, prefixes_path: str, task: str) -> None:
    """Score predictions against the truth file."""
    if task != "next-event":
        click.echo(f"v0 only scores 'next-event' (got {task})", err=True)
        sys.exit(1)
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


if __name__ == "__main__":
    main()
