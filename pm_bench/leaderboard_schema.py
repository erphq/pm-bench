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

import re
from collections.abc import Iterable

# Model names are rendered inside backticks in the markdown standings,
# go in URLs, and serve as primary keys. Restrict to a safe alphanumeric
# subset so a model literally named with a backtick can't break the
# table or escape any rendering context.
_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

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

    for key in ("task", "dataset", "metric", "scored_with"):
        if key in board and not isinstance(board[key], str):
            errors.append(
                _err_path(
                    f"$.{key}",
                    f"must be a string, got {type(board[key]).__name__}",
                )
            )

    if "task" in board and isinstance(board["task"], str) and board["task"] not in VALID_TASKS:
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
            seen_models: set[str] = set()
            for i, entry in enumerate(board["entries"]):
                errors.extend(_validate_entry(entry, i))
                # Names must be unique per board so standings have a
                # canonical row per submission. Duplicates almost
                # always mean the user copy-pasted and forgot to rename.
                if isinstance(entry, dict):
                    model = entry.get("model")
                    if isinstance(model, str):
                        if model in seen_models:
                            errors.append(
                                _err_path(
                                    f"$.entries[{i}].model",
                                    f"duplicate model name {model!r} (already "
                                    "used in an earlier entry)",
                                )
                            )
                        seen_models.add(model)

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

    if "model" in entry:
        model = entry["model"]
        if not isinstance(model, str):
            yield _err_path(f"{base}.model", "must be a string")
        elif not _MODEL_NAME_RE.match(model):
            yield _err_path(
                f"{base}.model",
                f"model name {model!r} must match [A-Za-z0-9._-]+ — names "
                "render inside markdown backticks and serve as primary keys",
            )

    if "predictions_path" in entry:
        pp = entry["predictions_path"]
        if not isinstance(pp, str):
            yield _err_path(f"{base}.predictions_path", "must be a string")
        else:
            # Reject absolute paths and `..` traversal: the leaderboard
            # JSON is checked into a repo, so predictions live alongside
            # it. Allowing arbitrary filesystem paths would let a
            # malicious entry trigger reads of files outside the repo.
            if pp.startswith("/") or pp.startswith("\\") or len(pp) >= 2 and pp[1] == ":":
                yield _err_path(
                    f"{base}.predictions_path",
                    f"must be a relative path; got absolute {pp!r}",
                )
            elif ".." in pp.replace("\\", "/").split("/"):
                yield _err_path(
                    f"{base}.predictions_path",
                    f"must not traverse with `..`; got {pp!r}",
                )
