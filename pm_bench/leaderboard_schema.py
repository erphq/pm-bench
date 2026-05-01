"""Lightweight schema validator for leaderboard JSON files.

Deliberately not pulling in a full JSON Schema implementation — the
files are simple enough that a hand-rolled checker gives clearer error
messages and keeps the dependency surface to stdlib only. If the schema
grows to need full JSON Schema features (refs, conditionals), swap this
for `jsonschema` and put it behind a `[dev]` extra.

The validator returns a list of error strings (empty = clean). Callers
decide whether to print them, fail loudly, or accumulate across files.
"""
from __future__ import annotations

from collections.abc import Iterable

VALID_TASKS: set[str] = {
    "next-event",
    "remaining-time",
    "outcome",
    "bottleneck",
    "conformance",
}

REQUIRED_TOP_KEYS: tuple[str, ...] = (
    "task",
    "dataset",
    "metric",
    "scored_with",
    "split",
    "entries",
)
REQUIRED_ENTRY_KEYS: tuple[str, ...] = (
    "model",
    "version",
    "predictions_path",
    "score",
)


def _err_path(prefix: str, problem: str) -> str:
    return f"{prefix}: {problem}"


def validate_board(board: dict) -> list[str]:
    """Return a list of validation errors. Empty list = clean."""
    errors: list[str] = []

    for key in REQUIRED_TOP_KEYS:
        if key not in board:
            errors.append(_err_path("$", f"missing required key {key!r}"))

    if "task" in board and board["task"] not in VALID_TASKS:
        errors.append(
            _err_path(
                "$.task",
                f"unknown task {board['task']!r}; expected one of "
                f"{sorted(VALID_TASKS)!r}",
            )
        )

    if "entries" in board:
        if not isinstance(board["entries"], list):
            errors.append(_err_path("$.entries", "must be a list"))
        else:
            for i, entry in enumerate(board["entries"]):
                errors.extend(_validate_entry(entry, i))

    if "split" in board:
        split = board["split"]
        if not isinstance(split, dict):
            errors.append(_err_path("$.split", "must be an object"))
        elif "kind" not in split:
            errors.append(_err_path("$.split", "missing required key 'kind'"))

    return errors


def _validate_entry(entry: object, idx: int) -> Iterable[str]:
    base = f"$.entries[{idx}]"
    if not isinstance(entry, dict):
        yield _err_path(base, "must be an object")
        return

    for key in REQUIRED_ENTRY_KEYS:
        if key not in entry:
            yield _err_path(base, f"missing required key {key!r}")

    if "score" in entry and not isinstance(entry["score"], dict):
        yield _err_path(f"{base}.score", "must be an object")

    if "model" in entry and not isinstance(entry["model"], str):
        yield _err_path(f"{base}.model", "must be a string")

    if "predictions_path" in entry and not isinstance(entry["predictions_path"], str):
        yield _err_path(f"{base}.predictions_path", "must be a string")
