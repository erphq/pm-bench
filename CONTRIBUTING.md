# Contributing to pm-bench

Thanks for considering a contribution. The most common path is **adding
a leaderboard entry** for a model you've trained — that's documented in
full below. If you want to fix a bug, add a baseline, or wire a new
dataset, the same pre-flight rules apply: tests pass, ruff is clean,
the leaderboard is verified.

## Setup

```bash
git clone https://github.com/erphq/pm-bench
cd pm-bench
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

`pytest -q` should report all-green. If it doesn't, please open an
issue before opening a PR — we want to know about a broken main.

## Adding a leaderboard entry

This is the supported submission flow. Same five steps for every task.

### 1. Run your model

Generate predictions on the canonical split. Either pipe through
`pm-bench prefixes` to get the truth file shape, or — if you trained on
your own pipeline — produce a CSV that matches the format below.

The standard recipe with the bundled dataset:

```bash
pm-bench split synthetic-toy > split.json
pm-bench prefixes synthetic-toy --split split.json --out prefixes.csv \
    --task <next-event|remaining-time|outcome|bottleneck>
# ... your model produces predictions.csv against prefixes.csv ...
```

For `conformance`, the submission is a model JSON (DFG transitions),
not per-prefix predictions. See `pm_bench/conformance.py` for the
schema; `pm-bench discover --baseline dfg` is a worked example.

### 2. Predictions file format

| Task | File | Columns |
|---|---|---|
| `next-event` | `predictions.csv[.gz]` | `case_id,prefix_idx,predictions` (predictions = `\|`-joined ranked list) |
| `remaining-time` | `predictions.csv[.gz]` | `case_id,prefix_idx,predicted_days` |
| `outcome` | `predictions.csv[.gz]` | `case_id,prefix_idx,score` (P(outcome=1)) |
| `bottleneck` | `predictions.csv[.gz]` | `activity_a,activity_b,predicted_wait_seconds` |
| `conformance` | `model.json` | `{"transitions": [["a","b"], ...]}` |

Predictions must cover every `(case_id, prefix_idx)` (or transition)
present in the truth file. Missing rows fail the score command and
make your submission un-rankable.

### 3. Score it locally

```bash
pm-bench score predictions.csv --prefixes prefixes.csv --task <task>
```

For conformance:

```bash
pm-bench score model.json --task conformance \
    --dataset synthetic-toy --split split.json
```

Record the resulting JSON — those are the numbers that go in the
leaderboard entry.

### 4. Add the entry

Check your predictions in:

```
leaderboard/predictions/<task>/<dataset>/<your-model-name>.<csv.gz|json>
```

Append an entry to `leaderboard/<task>/<dataset>.json`:

```json
{
  "model": "your-model-name",
  "version": "1.0.0",
  "predictions_path": "leaderboard/predictions/<task>/<dataset>/<your-model-name>.csv.gz",
  "code": "https://github.com/<you>/<repo>",
  "paper": "https://arxiv.org/abs/...",
  "score": { ...numbers from step 3... },
  "scored_at": "2026-MM-DDTHH:MM:SSZ",
  "notes": "What's interesting about this submission."
}
```

### 5. Verify and regenerate STANDINGS.md

```bash
pm-bench leaderboard --all --verify
pm-bench leaderboard --all --markdown > STANDINGS.md
```

Both must succeed before the PR can land — CI runs them. Open the PR
with a one-line summary of the result and how it compares to the
existing reference.

## Pre-PR checklist

- [ ] `pytest -q` passes locally
- [ ] `ruff check pm_bench tests` is clean
- [ ] `pm-bench leaderboard --all --verify` exits 0 (no drift)
- [ ] `STANDINGS.md` is regenerated if you touched any leaderboard JSON
- [ ] Git commit message describes the *why*, not just the *what*
- [ ] PR title is short (~50 chars); details go in the body

## Quantifying noise (for serious submissions)

Before claiming "X beats the baseline by N points," check the noise
band:

```bash
python -m bench.seeds --n 30
```

If your gain is smaller than the baseline's std band on the same task,
your number isn't a signal yet — keep iterating, or run more seeds and
report a CI alongside the headline.

## Code style

- Pure CPython where possible; torch / scipy / pandas live behind a
  `[ml]` extra (not yet shipped — open an issue first if your model
  needs it inside `pm_bench/`).
- Type hints on all public functions.
- Comments explain *why*, not *what*. The code should already say what.
- One feature per PR. Stacked PRs are fine if each can be reviewed in
  isolation.

## Reporting bugs

Open an issue. Please include:

- Python version (`python --version`)
- pm-bench version (`pm-bench --version`)
- The smallest command sequence that reproduces the issue
- The full traceback if there is one
