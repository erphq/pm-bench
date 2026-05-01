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

- **Round-4 polish** (`round4-polish` branch).
  - `pm-bench compare` now annotates each metric delta with
    `direction: "higher_is_better" | "lower_is_better"` and an
    `improved: bool` flag (only for metrics with a known direction —
    counts like `n` are left unannotated). Previously the JSON
    output had only the raw delta, leaving the consumer to remember
    which sign meant "better" per metric.
  - 3 new tests covering both directions + the no-direction case.
- **Round-3 cleanup** (`round3-fixes` branch). Another sweep turned up
  data-corruption and silent-misuse paths the first two passes missed:
  - `|` (PREFIX_SEP) in any activity name silently corrupted the
    predictions / prefixes round-trip → writers now raise ValueError.
  - `score_outcome` with non-binary truth labels silently treated
    them as negative → now raises with the offending index.
  - NaN / Inf in any score-fn input silently produced NaN/inf
    output (and a non-spec leaderboard JSON) → all three numeric
    score fns reject non-finite values up front.
  - Duplicate `(case_id, prefix_idx)` (or `(a, b)` for bottleneck)
    in predictions silently overwrote in the lookup-build → caught
    in the rescore helpers AND the score CLI; surfaces as exit 2.
  - Schema accepted duplicate model names within a board → caught.
  - Schema accepted `null` / non-string in required string fields
    (`task`, `dataset`, `metric`, `scored_with`) → typed checks added.
  - Mixed-type `case_ids` (int + str) raw-`TypeError`'d at sort →
    `_sorted_case_ids` helper now raises a clear "same type" error.
  - Dead `_run_one_callable` re-export in `bench/seeds.py` removed.
  - 9 new tests; 175 total, ruff clean.
- **Second-pass cleanup** (`second-pass-fixes` branch).
  After the first audit landed, a fresh sweep turned up 5 more bugs:
  - `score_bottleneck` silently returned 0 on all-zero truth →
    raises ValueError (degenerate dataset is undefined, must surface).
  - `pm-bench validate` on a non-JSON file raw-tracebacked → exits 2
    cleanly with file path + parse error.
  - `--out path/to/missing/dir/x.csv` now auto-creates the parent
    directory in `_open_text`'s write path.
  - `pm-bench compare` on a non-board JSON raw-tracebacked → exits 2.
  - Bad-shape split files (missing train/val/test) raw-tracebacked
    on the 5 commands that read them → centralized `_load_split`
    helper validates shape + exits 2 cleanly.
  - `bench.seeds.variance(n_seeds=0)` raw-IndexError → ValueError.
  - 9 new tests for these paths; 166 total, ruff clean.
- **Audit cleanup** (`audit-cleanup` branch).
  Independent agent reviewed 22 stacked PRs and surfaced 20 issues; this
  PR fixes the 14 high-priority ones:
  - `extract_prefixes` / `extract_remaining_time_targets` /
    `extract_outcome_targets` now sort `case_ids` before iterating, so
    regenerating reference predictions produces byte-identical output
    (was non-deterministic via `set` iteration order). All 8
    checked-in `.csv.gz` files regenerated against the new order.
  - One shared `_open_text(path)` helper in `predictions.py` handles
    `.gz` transparently. Every CSV reader/writer in `pm_bench/`
    routes through it, including `read_predictions_csv` itself, which
    means `pm-bench score predictions.csv.gz` now works end-to-end —
    matching what CONTRIBUTING.md has claimed all along.
  - `leaderboard.py` `_rescore_*` helpers no longer have a parallel
    `gzip.open` codepath; they call the shared readers, so the score
    CLI and the rescore path are guaranteed to read predictions
    identically.
  - `read_csv_log` strips UTF-8 BOMs (`utf-8-sig`) and normalizes
    away tzinfo so mixed-tz CSVs don't blow up downstream.
  - `pm-bench score` wraps its body in one `try/except` so KeyError
    (bad predictions header) and ValueError (length mismatch, bad
    model JSON) all exit 2 with a clean message, regardless of task.
  - `pm-bench compare` now exits 2 (not 1) on cross-task comparisons.
  - `pm-bench leaderboard --all --markdown --verify` now actually
    runs verify before printing markdown — was silently skipping.
  - `pm-bench validate` reads its file once via `Path.read_text`.
  - README "MAE weighted by case length" claim was wrong (the code
    is per-prefix equally weighted) — fixed.
  - README "Datasets" table now carries an explicit status note that
    the seven public logs need a one-time TOS-gated fetch first.
  - Tests added: drift on `entries[1]` (multi-entry blind spot was
    real), `--baseline X --task Y` mismatch errors (4 paths), score
    CLI missing-rows + malformed-header + bad model JSON, `--all
    --markdown --verify` interaction, BOM CSV, mixed-tz CSV, gz
    score path. 157 total, ruff clean.
- **Floor baselines on outcome + bottleneck — every board multi-entry**
  (`last-two-floors` branch).
  - `global` for outcome: predicts the training positive rate for
    every prefix → AUC = 0.5 by tied ranks. Sits below prior-ref.
  - `random` for bottleneck: deterministic SHA-256-based pseudo-random
    score per (a,b) transition → NDCG@10 0.943 vs mean-wait-ref's
    0.991. Stable across CI runs.
  - All 5 leaderboard boards now have 2 entries; multi-entry sort
    asserted across every task.
  - 147 total tests, ruff clean. STANDINGS regenerated.
- **`pm-bench validate <board.json>`** (`validate-command` branch).
  - One-shot pre-flight: schema check + score rescore on a single
    leaderboard file. Exits 0 / 2 with clear schema-prefixed or
    score-prefixed errors.
  - `--no-rescore` for a fast schema-only sanity check.
  - 4 new tests; 147 total, ruff clean.
  - CONTRIBUTING.md now points at it as the recommended pre-PR step.
- **JSON Schema for leaderboard files** (`leaderboard-schema` branch).
  - `pm_bench/leaderboard_schema.py:validate_board(dict) → list[str]`
    — stdlib-only structural checker; clear error paths
    (`$.entries[2].score`).
  - Parametrized test exercises every checked-in board against the
    schema; 4 negative tests catch missing top keys, unknown tasks,
    missing score, non-dict score.
  - 9 new tests; 143 total, ruff clean.
- **`synthetic-toy@<seed>` syntax** (`synthetic-seed-flag` branch).
  - Pass `synthetic-toy@99` to any command that takes a dataset name
    and the generator runs at that seed (default still seed=42 for
    canonical leaderboard runs).
  - Lets users do quick variance experiments without scripting Python
    or polluting the CLI with a `--seed` flag on every verb.
  - 2 new tests; 134 total, ruff clean.
- **CONTRIBUTING.md** (`contributing-doc` branch).
  - Step-by-step submission walkthrough: pipeline commands per task,
    file format table, pre-PR checklist, noise-quantification call
    via `bench.seeds`.
  - README points at it from the "Submitting" section.
- **`bench/seeds.py` cross-seed variance harness** (`seeds-variance`
  branch).
  - `python -m bench.seeds --n 30` runs each baseline at 30 seeds of
    the synthetic generator and prints mean / std / min / max per
    metric. Quantifies the noise band any "real" submission must
    clear to be statistically interesting.
  - First measurement (n=5): markov top-1 0.9183 ± 0.0111, mean-time
    MAE 1.284 ± 0.045, prior outcome AUC 0.634 ± 0.005, mean-wait
    NDCG@10 0.927 ± 0.017, dfg F 0.988 ± 0.024.
  - 4 new tests; 132 total, ruff clean.
- **HTTP fetch test** (`http-fetch-test` branch). Daemon-threaded
  http.server on an ephemeral port; verifies ensure_cached's
  download + cache-hit path. 124 tests.
- **`pm-bench compare board_a.json board_b.json`** (`compare-command`
  branch).
  - Diff two leaderboard JSON files. Per-model score deltas as JSON;
    models unique to one side surfaced separately.
  - Tasks/datasets must match (errors loudly otherwise) — prevents
    accidental cross-task comparisons.
  - 6 new tests; 123 total, ruff clean.
- **Floor baselines for time + conformance** (`floor-baselines` branch).
  - `zero-time` for remaining-time: predicts 0 days for every prefix.
    MAE 2.741 on synthetic-toy - exactly twice mean-ref's 1.348, as
    expected for a constant zero predictor.
  - `empty` for conformance: submits a model with no transitions.
    F = 0 by construction; the absolute conformance floor.
  - Both wired through CLI (`predict --baseline zero`, `discover
    --baseline empty`) and added as second entries on their boards.
    3 of 5 boards now demonstrate >1 entry; outcome and bottleneck
    still single-entry pending future submissions.
- **Uniform second baseline + multi-entry leaderboard demo**
  (`uniform-baseline` branch).
  - `pm_bench/baselines/uniform.py` - ranks every training-set
    activity in lexicographic order, identical for every prefix. The
    "didn't read the trace at all" floor.
  - `predict --baseline uniform` for next-event.
  - `leaderboard/next-event/synthetic-toy.json` now has **2 entries**:
    markov-ref top-1 0.9304 vs uniform-ref top-1 0.2025. Standings
    sort puts markov on top.
  - Demonstrates the leaderboard scales to multiple submissions on
    one (task, dataset) pair - a precondition for accepting external
    submissions.
  - 1 new test asserting the standings order; 117 total.
- **`pm-bench stats <name>`** (`stats-command` branch).
  - One-shot summary stats for any log: n_cases, n_events,
    n_activities, time span, mean/median case length, top-N
    activities and transitions.
  - Pure CPython; works on synthetic-toy and any CSV path the
    existing `_load_events` accepts.
  - 7 new tests; 116 total.
- **Synthetic-toy bumped to 200 cases - outcome row finally lands**
  (`synthetic-200` branch).
  - `synthetic_log()` default `n_cases` = 200 (was 50). Test partition
    now has ~45 positive cases (`delivery_confirmed`) so AUC is
    meaningful instead of degenerating to 0.5.
  - All 4 existing reference predictions regenerated and re-scored.
    New numbers: markov-ref top-1 0.9304 (was 0.9756 on 50 cases),
    mean-ref MAE 1.3481, mean-wait-ref NDCG@10 0.9911,
    dfg-ref F=1.0 (both partitions now cover the full path graph).
  - **5th leaderboard board added**: `outcome/synthetic-toy.json`
    with `prior-ref` entry - AUC 0.6319, n_pos 45 / 158. Real floor
    for any temporal model on the outcome task.
  - `_rescore_outcome` + `_outcome_truth_for_dataset` added to
    `leaderboard.py`. `pm-bench leaderboard --all --verify` now
    walks all 5 boards.
  - STANDINGS.md regenerated. 109 tests, ruff clean.
- **Conformance task - v0.3 closed** (`conformance-task` branch).
  - `score_conformance` - DFG fitness × precision → F-score. Pure
    CPython; no pm4py dep.
  - `pm_bench/conformance.py` - DFG extraction, model JSON r/w. The
    submission format is a JSON file with a `transitions` list.
  - `pm-bench discover <name> --baseline dfg --out model.json` -
    discovers the DFG from training cases. CLI `score --task
    conformance --dataset NAME --split split.json model.json` runs
    the comparison (the only score path that doesn't take
    `--prefixes`, since the model is a global structure).
  - `leaderboard/conformance/synthetic-toy.json` with the dfg-ref
    entry (F=0.857, fitness 1.0, precision 0.75 at the time; the
    synthetic-toy bump in the next branch pushed both partitions to
    cover the full path graph, lifting F to 1.0); 4 boards now
    verify under `--all`.
  - `pm-bench leaderboard --markdown` learns a conformance table
    column set; STANDINGS.md regenerated.
  - 11 new tests (`test_conformance.py`); 108 total, ruff clean.
- **CSV ingest** (`csv-ingest` branch).
  - `pm_bench/io.py:read_csv_log` - CSV / `.csv.gz` event-log loader
    that accepts both pm-bench-native column names (`case_id`,
    `activity`, `timestamp`) and PM4Py XES-derived names
    (`case:concept:name`, `concept:name`, `time:timestamp`).
  - `_load_events` auto-detects path-like inputs (`/`, `.csv`,
    `.csv.gz`, `.tsv`) and routes to the loader; existing registry
    names still work. `pm-bench split path/to/log.csv` runs the
    full split → prefixes → predict → score loop on an arbitrary
    CSV without registry plumbing.
  - 8 new tests including a click-runner end-to-end. 97 total.
- **STANDINGS.md auto-generation** (`standings-md` branch).
  - `pm-bench leaderboard --all --markdown` emits a markdown doc
    listing every board with a task-aware table.
  - `STANDINGS.md` checked into the repo; a CI test asserts it
    matches what `--all --markdown` produces today (regenerate with
    `pm-bench leaderboard --all --markdown > STANDINGS.md`).
  - README links to STANDINGS so the headline numbers are one click
    away. v0.4 milestone closed.
- **Bottleneck task (NDCG@10 over transitions)** (`bottleneck-task` branch).
  - `score_bottleneck` - pure-CPython NDCG@k with average DCG/IDCG
    discounting. Missing predictions sink to the bottom of the
    ranking (model that refuses to predict can't claim credit).
  - `pm_bench/bottleneck.py` - per-transition mean-wait targets.
    Truth shape is `(activity_a, activity_b, mean_wait_seconds,
    n_observations)` - different from the per-prefix tasks.
  - `pm_bench/baselines/mean_wait.py` - train-mean-per-transition
    with global-mean fallback. On synthetic-toy: NDCG@10 0.9786 over
    6 transitions. Strong floor for any temporal model.
  - CLI: `--task bottleneck`, `--baseline mean-wait`, end-to-end.
  - `leaderboard/bottleneck/synthetic-toy.json` with the mean-wait-ref
    entry; `pm-bench leaderboard --all --verify` now walks 3 boards.
  - 7 new tests (`test_bottleneck.py`); 86 total, ruff clean.
- **Outcome task (binary AUC)** (`outcome-task` branch).
  - `score_outcome` - pure-CPython rank-sum AUC, with average-rank
    tie-breaking; degenerate single-class case returns 0.5 by
    convention rather than NaN.
  - `pm_bench/baselines/prior_outcome.py` - last-activity-conditioned
    positive rate (with global-rate fallback for unseen activities).
    The dumbest baseline that uses *any* prefix signal.
  - CLI: `--task outcome`, `--baseline prior`, end-to-end through
    `prefixes / predict / score`.
  - Per-dataset outcome rule registered for synthetic-toy
    (`is_positive_outcome`: case ends with `delivery_confirmed`).
  - **No leaderboard entry yet** - synthetic-toy with seed=42 happens
    to have zero positives in the test partition, so AUC degenerates.
    The pipeline runs end-to-end and the test asserts it; a real
    leaderboard entry waits on a pinned BPI dataset.
  - 8 new tests; 73 total, ruff clean.
- **Remaining-time task** (`remaining-time` branch).
  - `score_remaining_time` (MAE in days), prefixes/predictions
    formats parallel to next-event so models share a loader.
  - `pm_bench/baselines/mean_time.py` - mean-of-train reference.
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
  - `pm_bench/leaderboard.py` - load/rescore/verify/standings, all
    pure CPython; reads gzipped or plain CSV.
  - CLI: `pm-bench leaderboard <task> <dataset> [--verify]` -
    pretty-prints standings, optionally re-runs scoring.
  - 8 new tests, including a drift-detection canary that tampers with
    the recorded score and confirms `verify` flags it.
- **v0.1 fetch + hash machinery** (`dataset-fetch` branch).
  - `pm_bench/cache.py` - cache root resolution
    (`$PM_BENCH_CACHE` → `~/.cache/pm-bench/`), per-dataset path with
    correct extension by format.
  - `pm_bench/fetch.py` - `ensure_cached(dataset)` covers the four
    cases: cached+match, cached+mismatch (loud failure),
    cached+unpinned (returns actual hash), not-cached (auto-download
    if URL set, otherwise raise `ManualFetchRequired`). Streams in
    1 MiB chunks; atomic `.part`-then-rename writes; sha256 verified
    against the registry pin.
  - CLI `pm-bench fetch <name> [--pin]` - prints status, emits a
    pasteable `registry.yml` patch when `--pin` is set.
  - 13 new tests across `test_cache.py` and `test_fetch.py`. 37 total.
- **End-to-end loop on synthetic-toy** (`end-to-end-loop` branch,
  PR #2).
  - `pm_bench/prefixes.py` - extract prediction targets from a split,
    write/read CSV. Skips length-1 cases.
  - `pm_bench/predictions.py` - predictions CSV format
    (`case_id,prefix_idx,predictions`).
  - `pm_bench/baselines/markov.py` - first-order Markov reference
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
  first dataset - keeps `pip install pm-bench` fast for users who
  only need scoring.
- No leaderboard CI yet (v0.4). The file formats are stable, so this
  is "wire up a workflow that runs `pm-bench score`" - orthogonal to
  the dataset work.
