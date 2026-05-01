# Leaderboard

Standings JSON files live under `leaderboard/<task>/<dataset>.json`.

Each file describes:
- the task and metric
- the split convention (case-level chronological is the only blessed
  one in v0)
- a list of submission entries, each with: model name, version, code
  link, predictions file, score, and timestamp

Reference baselines that ship with `pm-bench` keep their predictions
checked in under `leaderboard/predictions/<task>/<dataset>/<model>.csv.gz`,
so the loop is reproducible without hitting the network.

## Verifying a leaderboard file

```bash
pm-bench leaderboard next-event synthetic-toy --verify
```

This re-scores every entry by reading its `predictions_path` (relative
to the repo root) and the dataset's prefixes file, then asserts the
recorded `score` matches what `pm_bench.score` produces today.
Any drift fails loudly - pinned numbers must match the code that
produced them.

## Submitting

Today (pre-v0): open a PR adding a new entry to the relevant JSON
file, with your `predictions.csv.gz` checked in under
`leaderboard/predictions/...`. Once the leaderboard CI is wired
(v0.4) submissions will move to a URL-based flow where CI fetches the
predictions and fills in the score.

## Score convention

The `score` block on each entry carries different keys per task. All
score floats live in `[0, 1]` unless noted. `n` (or `n_transitions`)
makes split sizes auditable across entries — if your count differs
from the reference, you used a different split.

| Task | Score keys | Direction |
|---|---|---|
| `next-event` | `top1`, `top3`, `n` | higher is better |
| `remaining-time` | `mae_days`, `n` | **lower** is better |
| `outcome` | `auc`, `n`, `n_pos` | higher is better |
| `bottleneck` | `ndcg_at_k`, `k`, `n_transitions` | higher is better |
| `conformance` | `fscore`, `fitness`, `precision`, `n_test_transitions`, `n_model_transitions` | higher is better |

`pm-bench compare` annotates each metric delta with `direction` and
`improved` so callers don't have to remember which way is up.
