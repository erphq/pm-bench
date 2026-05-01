# Status

_Last updated: 2026-04-30._

## Where we are

Pre-v0. Three pieces shipped on top of v0.0:

1. The end-to-end loop runs on the bundled `synthetic-toy` dataset
   (split → prefixes → predict → score; Markov reference baseline
   gets top-1 0.976, top-3 1.000).
2. The fetch + hash + cache machinery is in place. `pm-bench fetch
   <name>` resolves a dataset to a local path, verifies the registry
   sha256, and prints precise instructions for the TOS-gated download
   step on 4TU / Mendeley. `--pin` emits the `registry.yml` patch a
   contributor pastes into a PR after the manual download.
3. The leaderboard scaffold is live: standings JSON under
   `leaderboard/<task>/<dataset>.json`, reference predictions checked
   in under `leaderboard/predictions/...`, and `pm-bench leaderboard
   <task> <dataset> [--verify]` re-scores entries to catch drift. The
   Markov-ref entry on `synthetic-toy` is the first row, and a
   determinism test in CI fails if the recorded score doesn't match a
   fresh rescore.

What's still left in v0.1 is purely a per-dataset operational task: do
the one-time download, run `--pin`, open seven small PRs to pin the
hashes, then wire the XES parser to `_load_events` so `split`/
`prefixes`/`predict` work on real BPI data. None of it requires
further code design.

A submission today on the bundled toy:

```bash
pm-bench split synthetic-toy > split.json
pm-bench prefixes synthetic-toy --split split.json --out prefixes.csv
pm-bench predict synthetic-toy --split split.json \
  --prefixes prefixes.csv --out predictions.csv --baseline markov
pm-bench score predictions.csv --prefixes prefixes.csv --task next-event
# → top1 0.976, top3 1.000
```

The fetch flow on a TOS-gated dataset:

```bash
pm-bench fetch bpi2020
# → bpi2020: no download_url (TOS-gated). Visit https://data.4tu.nl/...,
#   accept the terms, and save the archive to ~/.cache/pm-bench/bpi2020.xes.gz.
#   Then re-run `pm-bench fetch bpi2020 --pin` to compute the sha256.

# (manual download + place in cache dir)

pm-bench fetch bpi2020 --pin
# → bpi2020: cached at ~/.cache/pm-bench/bpi2020.xes.gz (unpinned)
#   sha256: <hex>
#
#   # paste under the matching dataset entry in pm_bench/registry.yml:
#     - name: bpi2020
#       sha256: <hex>
```

## Recently shipped

- **STANDINGS.md auto-generation** (`standings-md` branch).
  - `pm-bench leaderboard --all --markdown` emits a markdown doc
    listing every board with a task-aware table.
  - `STANDINGS.md` checked into the repo; a CI test asserts it
    matches what `--all --markdown` produces today (regenerate with
    `pm-bench leaderboard --all --markdown > STANDINGS.md`).
  - README links to STANDINGS so the headline numbers are one click
    away. v0.4 milestone closed.
- **Bottleneck task (NDCG@10 over transitions)** (`bottleneck-task` branch).
  - `score_bottleneck` — pure-CPython NDCG@k with average DCG/IDCG
    discounting. Missing predictions sink to the bottom of the
    ranking (model that refuses to predict can't claim credit).
  - `pm_bench/bottleneck.py` — per-transition mean-wait targets.
    Truth shape is `(activity_a, activity_b, mean_wait_seconds,
    n_observations)` — different from the per-prefix tasks.
  - `pm_bench/baselines/mean_wait.py` — train-mean-per-transition
    with global-mean fallback. On synthetic-toy: NDCG@10 0.9786 over
    6 transitions. Strong floor for any temporal model.
  - CLI: `--task bottleneck`, `--baseline mean-wait`, end-to-end.
  - `leaderboard/bottleneck/synthetic-toy.json` with the mean-wait-ref
    entry; `pm-bench leaderboard --all --verify` now walks 3 boards.
  - 7 new tests (`test_bottleneck.py`); 86 total, ruff clean.
- **Outcome task (binary AUC)** (`outcome-task` branch).
  - `score_outcome` — pure-CPython rank-sum AUC, with average-rank
    tie-breaking; degenerate single-class case returns 0.5 by
    convention rather than NaN.
  - `pm_bench/baselines/prior_outcome.py` — last-activity-conditioned
    positive rate (with global-rate fallback for unseen activities).
    The dumbest baseline that uses *any* prefix signal.
  - CLI: `--task outcome`, `--baseline prior`, end-to-end through
    `prefixes / predict / score`.
  - Per-dataset outcome rule registered for synthetic-toy
    (`is_positive_outcome`: case ends with `delivery_confirmed`).
  - **No leaderboard entry yet** — synthetic-toy with seed=42 happens
    to have zero positives in the test partition, so AUC degenerates.
    The pipeline runs end-to-end and the test asserts it; a real
    leaderboard entry waits on a pinned BPI dataset.
  - 8 new tests; 73 total, ruff clean.
- **Remaining-time task** (`remaining-time` branch).
  - `score_remaining_time` (MAE in days), prefixes/predictions
    formats parallel to next-event so models share a loader.
  - `pm_bench/baselines/mean_time.py` — mean-of-train reference.
    On synthetic-toy: MAE 1.255 days. Floor for any temporal model.
  - CLI: `prefixes`, `predict`, `score` all dispatch on
    `--task {next-event,remaining-time}`. Single command surface,
    two tasks.
  - `leaderboard.py` rescore + standings handle both tasks; standings
    sorts ascending for MAE, descending for accuracy.
  - `leaderboard/remaining-time/synthetic-toy.json` with the
    mean-ref entry; reference predictions checked in alongside.
  - 8 new tests covering extraction, baseline determinism, CSV
    round-trip, e2e click-runner pipeline, and leaderboard verify.
    59 total.
- **Leaderboard CI workflow** (`leaderboard-ci` branch).
  - `pm-bench leaderboard --all [--verify]` walks every standings
    file under `leaderboard/` so contributors and CI run the same
    one command.
  - `.github/workflows/leaderboard.yml` runs that command on every
    push / PR that touches `leaderboard/` or `pm_bench/`. Drift in
    any standings file blocks merge with its own dedicated check.
  - 2 new tests cover the `--all` path on both clean and tampered
    trees. 47 total.
- **Leaderboard scaffold** (`leaderboard-scaffold` branch).
  - `leaderboard/next-event/synthetic-toy.json` with the Markov
    reference entry; predictions checked in under
    `leaderboard/predictions/next-event/synthetic-toy/markov-ref.csv.gz`.
  - `pm_bench/leaderboard.py` — load/rescore/verify/standings, all
    pure CPython; reads gzipped or plain CSV.
  - CLI: `pm-bench leaderboard <task> <dataset> [--verify]` —
    pretty-prints standings, optionally re-runs scoring.
  - 8 new tests, including a drift-detection canary that tampers with
    the recorded score and confirms `verify` flags it.
- **v0.1 fetch + hash machinery** (`dataset-fetch` branch).
  - `pm_bench/cache.py` — cache root resolution
    (`$PM_BENCH_CACHE` → `~/.cache/pm-bench/`), per-dataset path with
    correct extension by format.
  - `pm_bench/fetch.py` — `ensure_cached(dataset)` covers the four
    cases: cached+match, cached+mismatch (loud failure),
    cached+unpinned (returns actual hash), not-cached (auto-download
    if URL set, otherwise raise `ManualFetchRequired`). Streams in
    1 MiB chunks; atomic `.part`-then-rename writes; sha256 verified
    against the registry pin.
  - CLI `pm-bench fetch <name> [--pin]` — prints status, emits a
    pasteable `registry.yml` patch when `--pin` is set.
  - 13 new tests across `test_cache.py` and `test_fetch.py`. 37 total.
- **End-to-end loop on synthetic-toy** (`end-to-end-loop` branch,
  PR #2).
  - `pm_bench/prefixes.py` — extract prediction targets from a split,
    write/read CSV. Skips length-1 cases.
  - `pm_bench/predictions.py` — predictions CSV format
    (`case_id,prefix_idx,predictions`).
  - `pm_bench/baselines/markov.py` — first-order Markov reference
    baseline. Trained on the train partition only; falls back to
    unigram for unseen last-activities.
  - CLI gained `prefixes`, `predict`, `score`.
  - `tests/test_e2e.py` covers the loop end-to-end via the click
    runner; format changes will trip it.
- **v0.0** (initial release): scaffold, registry, case-chrono split,
  next-event scoring function, CLI `list` / `info` / `split`.

## Next up

- **One-time dataset pinning.** Per dataset (BPI 2012/2017/2018/2019/
  2020 collection, Sepsis, Helpdesk): accept the TOS, save to the
  cache, run `pm-bench fetch <name> --pin`, open the registry PR.
  This is the gate on every downstream milestone.
- **XES parser wiring.** `_load_events` currently rejects everything
  except `synthetic-toy`. Once a dataset is pinned, swap that branch
  for a pm4py-backed XES read (move pm4py to `[bpi]` extras so the
  base install stays light).
- **`gnn` as the second reference baseline.** `gnn`'s v0.5 milestone
  has been waiting for a pinned dataset registry, which `pm-bench`
  now provides the moment any single dataset is pinned.
- Additional tasks beyond next-event (remaining-time, outcome,
  conformance, bottleneck). The split + prefixes machinery is shared;
  scoring is the per-task piece.

## Known gaps

- The base install does not pull `pm4py`, so XES parsing isn't wired
  yet. Adding a `[bpi]` extra is the right move when we pin the
  first dataset — keeps `pip install pm-bench` fast for users who
  only need scoring.
- No leaderboard CI yet (v0.4). The file formats are stable, so this
  is "wire up a workflow that runs `pm-bench score`" — orthogonal to
  the dataset work.
