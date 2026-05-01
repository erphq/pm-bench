"""CLI for pm-bench."""
from __future__ import annotations

import json
import sys

import click

from pm_bench import _synth
from pm_bench.registry import get_dataset, load_registry
from pm_bench.split import case_chrono_split


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
@click.option("--task", default="next-event", show_default=True)
def split(name: str, task: str) -> None:
    """Produce a train/val/test split for a dataset.

    v0 supports `synthetic-toy` only; other datasets require manual fetch.
    """
    if name != "synthetic-toy":
        click.echo(
            f"v0 only supports 'synthetic-toy' (got {name}); see README for the v0.1 milestone",
            err=True,
        )
        sys.exit(1)
    events = list(_synth.synthetic_log())
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


if __name__ == "__main__":
    main()
