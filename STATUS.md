# Status

_Last updated: 2026-05-01 — XES parser + dispatch wiring shipped._

## Where we are

**v0.4 live, v0.5 partially unblocked.** All five v0 tasks ship with
reference + floor baselines on `synthetic-toy`. **An XES parser is
now in-tree** (stdlib only — no pm4py dep) so the moment a real BPI
dataset gets pinned, the only remaining work is a one-line dispatch
in `_events_and_test_cases` per dataset.

`_load_events` now handles 4 input shapes: bundled `synthetic-toy`,
`.csv`/`.csv.gz` paths, **`.xes`/`.xes.gz` paths**, and
registry-named datasets (auto-fetches via the cache + sha256
machinery, parses by registry `format`).

**240 tests** pass, ruff clean, all 5 leaderboard boards verify.

```bash
$ pm-bench leaderboard --all --verify
bottleneck/synthetic-toy: OK - 2 entry(ies)
conformance/synthetic-toy: OK - 2 entry(ies)
next-event/synthetic-toy: OK - 2 entry(ies)
outcome/synthetic-toy: OK - 2 entry(ies)
remaining-time/synthetic-toy: OK - 2 entry(ies)
```

A submission today on the bundled toy:

```bash
pm-bench split synthetic-toy > split.json
pm-bench prefixes synthetic-toy --split split.json --out prefixes.csv
pm-bench predict synthetic-toy --split split.json \
  --prefixes prefixes.csv --out predictions.csv --baseline markov
pm-bench score predictions.csv --prefixes prefixes.csv --task next-event
# → top1 0.9304, top3 1.0000  (markov-ref on n_cases=200)
```

## What's pending

**v0.5 — first real dataset pin.** The fetch + hash + cache machinery
is fully in place. What remains is the one-time, per-dataset TOS-gated
download from 4TU / Mendeley:

```bash
# 1. Visit the dataset's landing URL (see `pm-bench info <name>`),
#    accept the TOS, save the archive to the path pm-bench prints.
pm-bench fetch bpi2020
# 2. Re-run with --pin to emit the registry.yml sha256 patch.
pm-bench fetch bpi2020 --pin
# 3. PR the patch + a per-dataset _events_and_test_cases dispatch.
```

Once one dataset lands pinned, `gnn` (companion repo) becomes a
landable second reference baseline (its v0.5 milestone unblocks the
moment any single pm-bench dataset is pinned).

**v1.0** — first external submissions; cited in ≥1 paper.

## Audit cascade summary

12 rounds of agent-led + manual audits surfaced ~60 distinct issues.
All addressed before merging the cleanup stack to main.

Categories covered:
- **Determinism**: sorted iteration, stable sort tiebreakers, lifted
  CSV field-size limit, deterministic regen of all reference
  predictions.
- **I/O safety**: `_open_text` (gz/BOM/utf-8/utf-8-sig everywhere),
  atomic CSV + JSON writes with PID+UUID staging, auto-mkdir on
  write, partial-download / partial-write cleanup.
- **Score correctness**: NaN/Inf rejected at write AND score time;
  AUC tie-breaking; NDCG zero-truth degeneracy; outcome non-binary
  rejection; length-mismatch + empty-input guards.
- **Schema rigor**: required keys, types (model/version/scored_at as
  ISO timestamp with time component, score values numeric not bool),
  model name regex, predictions_path no abs/no `..`/non-empty,
  split.kind whitelist with type check, duplicate model names
  caught, score-key/task consistency.
- **Error handling**: every CLI verb catches (KeyError, ValueError,
  TypeError, OSError, JSONDecodeError) → exit 2 with type-prefixed
  message; no raw tracebacks in any user-facing path.
- **Data validation**: BOM stripping, whitespace trim on every column
  (case_id / activity / true_next / ranked items / transition keys),
  pipe-bearing / empty activity rejected on write, duplicate
  prediction keys raise.
- **Concurrency**: PID+UUID-staged temp files in `fetch.py` and every
  CSV/JSON writer, atomic `Path.replace` for final landing.
- **Determinism CI**: `--all --verify` walks every board and exits
  non-zero on any drift; STANDINGS.md staleness is its own test.

See "Recently shipped" below for the per-round breakdown.

## Recently shipped

- **XES parser + dispatch wiring** (`xes-parser` branch).
  - `pm_bench/xes.py:read_xes_log` — stdlib-only XES reader using
    `xml.etree.ElementTree.iterparse` for bounded memory on 100MB+
    logs. Namespace-tolerant, tz-aware → UTC, surfaces malformed
    XML as `ValueError` (not `ExpatError`).
  - `_load_events` now dispatches XES paths and registry-named
    datasets (CSV or XES per `registry.yml` `format`). The fetch +
    cache + sha256 machinery auto-runs for registry names —
    submitters of a freshly-pinned dataset just call `pm-bench
    split bpi2020`.
  - `looks_like_path` recognizes `.xes` / `.xes.gz`.
  - 11 new tests; 240 total. Zero new dependencies.
  - **What's left for the first BPI pin**: download the .xes.gz from
    4TU (interactive TOS), `pm-bench fetch <name> --pin`, PR the
    sha256 + a per-dataset branch in `_events_and_test_cases`. The
    parser is ready.
- **Round-12 cleanup** (`round12-fixes` branch).
  - **R58**: ISO timestamp validator accepted bare dates
    (`"2026-04-30"` → parsed by `fromisoformat`, but no time
    component → too coarse to mark a scoring run). Now requires
    `T` or space.
  - **R59**: `_runtime_safe` exited with just the bare exception
    message. A swallowed implementation bug (KeyError from a typo)
    looked identical to a data error. Now prefixed with the
    exception type so the user can tell them apart.
  - 2 new tests + 1 new contract test for the empty-board markdown
    path. 229 total, ruff clean.
- **Round-11 cleanup** (`round11-fixes` branch). Eighth audit pass:
  - **R47**: `IsADirectoryError` / `PermissionError` (and other
    `OSError` subclasses) leaked as raw tracebacks past the
    `except FileNotFoundError` filters. All four catch sites
    (`_runtime_safe`, two leaderboard verify branches, validate's
    verify) widened to `except OSError`.
  - **R48**: schema accepted empty `predictions_path` (then crashed
    in `_open_text` with `IsADirectoryError`). Now requires
    non-empty.
  - **R49**: `write_model_json` was the one writer without atomic
    semantics. KeyboardInterrupt mid-write left a half-written
    `.json` / `.json.gz` at the destination. Now stages PID+UUID-
    suffixed tmp file and renames on success.
  - **R50**: prediction writers accepted NaN/Inf and round-tripped
    them as parseable strings; only the score function caught it
    later (after data was already on disk). Now writers reject
    non-finite values up-front.
  - **R51**: `_atomic_csv_write` used a process-shared `path + ".tmp"`
    suffix — concurrent writers to the same path would clobber each
    other's staging file. Same PID+UUID fix as `fetch.py:_download`.
  - **R52**: `read_csv_log` accepted empty `case_id` (silently
    aggregating phantom case). Now rejected, mirroring the
    empty-activity rule.
  - **R53**: `compare_boards` subtracted booleans (`isinstance(True,
    int)` is True). Schema rejects bools in scores; compare now
    skips them too.
  - **R55**: `scored_at` field accepted any string ("yesterday",
    "2026-13-01"). Schema now requires ISO 8601.
  - 4 new tests; 227 total, ruff clean.
- **Round-10 cleanup** (`round10-fixes` branch). Seventh audit pass:
  - **R44**: `write_model_json` ignored `.gz` and skipped parent
    mkdir. `discover --out new_dir/model.json` raw-FileNotFound'd;
    `discover --out model.json.gz` wrote plain JSON at a `.gz` path
    that `read_model_json` then crashed on. Fixed: now `.gz`-aware
    and auto-mkdirs, mirroring the CSV writers.
  - **R45**: `prefixes`, `predict`, `discover` had no outer
    try/except — bad inputs (malformed CSV, mixed-type case_ids)
    raw-tracebacked. New `_runtime_safe` decorator catches
    `(KeyError, ValueError, TypeError, FileNotFoundError)` → exit 2
    with a clean message. Wraps all three verbs.
  - **R46**: `compare` only caught `(JSONDecodeError, KeyError,
    ValueError)`. A JSON with `entries: "not a list"` raw-TypeError'd
    on iteration. Now caught.
  - 4 new tests; 223 total, ruff clean.
- **Round-9 cleanup** (`round9-fixes` branch). Sixth audit pass found
  another batch of corruption + traceback paths:
  - **R37+R38**: `csv.DictReader` returns `None` for missing columns
    in short rows. The 7 readers (event log, predictions, prefixes,
    time, outcome, bottleneck targets + predictions) all then
    `.strip()` / `int()` / `float()` on `None` → uncaught
    AttributeError / TypeError. New `_require_field(row, col, line, path)`
    helper raises ValueError with file:line:column context. Applied
    to every reader.
  - **R39**: validation failures mid-write (empty / pipe-bearing
    activity) left a partial CSV at the destination. New
    `_atomic_csv_write` stages to a tmp file (gz-aware naming) and
    renames on success; on exception, unlinks the tmp. All 7 writers
    use it.
  - **R40+R41**: `load_board` now rejects unknown `task` (used to
    fall through to next-event-shaped formatting and crash on
    `f"{None:.4f}"`). The single-board CLI path now catches
    `(JSONDecodeError, KeyError, ValueError, TypeError)` instead of
    only `FileNotFoundError`. The `--all` paths likewise widened.
  - **R42**: `verify` now reports keys-in-recorded-not-in-fresh as
    drift. A board with `task: outcome` but `top1` in the recorded
    score (logically incoherent) used to pass silently because the
    loop only iterated the keys produced by the scorer.
  - 4 new tests; 219 total, ruff clean.
- **Round-8 cleanup** (`round8-fixes` branch). 7 more bugs from a
  fresh agent-led audit:
  - **R30**: `read_prefixes_csv` and `read_predictions_csv` only
    stripped `case_id` whitespace; `true_next` and the activity
    elements of `prefix` / `ranked` were read raw. Padded values
    silently scored 0. Now uniformly stripped.
  - **R31**: `pm-bench info synthetic-toy@99` failed as "unknown
    dataset" — the only verb that didn't accept the `@<seed>`
    suffix. Now resolves to the base entry.
  - **R32**: `read_model_json` (conformance submissions) didn't
    accept `.json.gz`, but the schema didn't restrict the extension.
    A leaderboard entry pointing at `model.json.gz` would pass schema
    and then UTF-8-decode-error on the gzip bytes. Now `.gz`-aware.
  - **R33**: schema accepted non-string `version` and `scored_at`.
    Now type-checked.
  - **R34**: schema accepted non-numeric values inside `score`
    (e.g. `"top1": "0.5"`), which then crashed `math.isclose` at
    verify time. Now every score value must be `int|float`.
  - **R35**: `pm-bench split --task <task>` stamped a `task` field
    into the JSON that nothing read. Removed the `--task` flag and
    the field — the split is task-agnostic by design.
  - **R36**: `_load_split` validated key presence but not type. A
    `"train": "c1"` (string) would silently iterate as characters.
    Now requires lists.
  - 11 new tests; 215 total, ruff clean.
- **Round-7 cleanup** (`round7-baseline-tests` branch).
  - **Robustness gap from round 6**: 4 baseline functions
    (`fit_uniform`, `predict_zero_time`, `fit_global_rate` /
    `predict_global_rate`, `predict_random_rank`) had no direct unit
    tests — only indirect leaderboard-rescore coverage. 9 contract-
    pinning tests added in `test_baselines_units.py`.
  - **R28**: schema validator raw-TypeError'd when `split.kind` was
    a non-hashable type (e.g. list). Now: type-check before
    membership-check; emits "must be a string" error.
  - **R29**: spreadsheet-padded `case_id` (or `activity_a`/
    `activity_b` in bottleneck) in any of the 5 read paths
    (predictions, prefixes, time, outcome, bottleneck) silently
    failed to join against the truth file. Same `.strip()` fix as
    `read_csv_log` got in round 6, applied uniformly.
  - 11 new tests; 206 total, ruff clean.
- **Round-6 cleanup** (`round6-fixes` branch). Fourth audit pass found
  4 more real bugs:
  - **R24**: `pm-bench split --task` accepted any string (no
    `click.Choice`). The other commands have it; split was the only
    outlier and would silently stamp `"task": "bogus"` into split.json.
    Fixed.
  - **R25**: csv module's default 128 KiB per-field size limit
    hard-failed on legitimate long activity names with a cryptic
    `_csv.Error`. Lifted module-wide to 2 GiB in `pm_bench/__init__.py`.
  - **R26**: `read_csv_log` did not strip whitespace from `case_id` /
    `activity` / `timestamp`. A spreadsheet export with `" c1"`
    rows alongside `"c1"` rows would silently produce two distinct
    case ids and halve every metric. Now strips.
  - **R27**: `case_chrono_split` had no tiebreaker for cases with
    equal start timestamps — the partition depended on dict-iteration
    order, which depended on event-input order. Two orderings of the
    same input would produce different splits. Secondary sort by
    `case_id` added.
  - 4 new tests; 195 total, ruff clean.
- **Round-5 cleanup** (`round5-fixes` branch). A fresh agent-led audit
  found 9 more issues; this PR fixes them all:
  - **R14**: BOM-prefixed CSVs only worked for the event log, not for
    predictions / prefixes / time / outcome / bottleneck / model JSON.
    Centralized in `_open_text` (now `utf-8-sig` on read, `utf-8` on
    write); `read_model_json` and `load_board` use `utf-8-sig`. Excel-
    saved submissions round-trip now.
  - **R15**: locale-default text I/O on Windows (cp1252) would
    mojibake non-ASCII activity names. Every read/write is now
    explicitly encoded.
  - **R16**: `read_csv_log` stripped tzinfo without converting to UTC,
    silently reordering aware rows relative to naive ones in mixed-tz
    CSVs. Aware rows now `astimezone(UTC).replace(tzinfo=None)`.
  - **R17**: `read_model_json` accepted non-string transition pair
    elements (`["a", 1]`), producing silent fitness=0. Now raises with
    the offending types.
  - **R18**: concurrent `pm-bench fetch` of the same dataset would
    race on the `.part` file. Each process now uses
    `<dest>.<pid>-<uuid>.part` so the only contended op is the final
    atomic rename.
  - **R19**: `pm-bench fetch synthetic-toy@99` failed as "unknown
    dataset" while every other command accepted the suffix. Now
    matches synthetic-toy semantics ("generated on demand").
  - **R20**: score CLI duplicate-key error didn't name the offending
    key. Harmonized with the leaderboard rescore path's
    `_check_unique_pred_keys`.
  - **R21**: `bench/seeds.py` used population stdev where the
    documented use is inferential (single new run vs the band).
    Switched to sample stdev. STATUS numbers re-quoted.
  - **R22**: empty-string activity name silently lost on round-trip
    (it's the encoding's "no activities" sentinel). Writers now
    reject.
  - **R23**: `leaderboard/README.md` only documented next-event keys
    (`top1`/`top3`/`n`). Now covers all 5 tasks with direction.
  - 9 new tests; 191 total, ruff clean.
- **Round-4 polish (continued)** (`round4-polish` branch).
  - `pm-bench compare` now annotates each metric delta with
    `direction: "higher_is_better" | "lower_is_better"` and an
    `improved: bool` flag.
  - `pm-bench validate --repo-root <empty-dir>` (and `leaderboard
    --all --verify`, and the single-board `leaderboard --verify`)
    used to raw-traceback FileNotFoundError when the predictions
    files were missing under the chosen repo-root. All three paths
    now catch and report the missing path with exit 2.
  - `_download` cleans up the `.part` file on a partial-transfer
    failure rather than leaving an orphan blob in the cache dir.
  - 6 new tests; 181 total, ruff clean.
  - **R11**: model name with backticks / spaces broke markdown
    standings (model rendered inside markdown backticks). Schema
    now restricts model name to `[A-Za-z0-9._-]+`.
  - **R12**: absolute or `..`-traversing `predictions_path` was
    accepted, letting a malicious leaderboard JSON trigger reads
    outside the repo. Schema now rejects both shapes; the residual
    KeyError on a non-CSV file at the verify path is caught and
    surfaced as exit 2.
  - **R13**: `split.kind` previously accepted any string. Schema now
    requires it to be in `{case-chrono}` (the only convention
    pm-bench supports today; the set grows when we add more).
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
  - First measurement (n=5, sample stdev): markov top-1
    0.918 ± 0.012, mean-time MAE 1.284 ± 0.051, prior outcome AUC
    0.634 ± 0.005, mean-wait NDCG@10 0.927 ± 0.018, dfg F
    0.988 ± 0.026.
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

- **Pin one BPI dataset (v0.5 unblock).** Per dataset (BPI
  2012/2017/2018/2019/2020 collection, Sepsis, Helpdesk): accept the
  TOS, save to cache, run `pm-bench fetch <name> --pin`, PR the
  registry hash. The fetch + hash + atomic-write machinery is all in
  place; this is purely the one-time human step.
- **XES parser wiring.** Once a dataset is pinned, extend
  `_load_events` with a pm4py-backed XES branch behind a `[bpi]`
  extra (keeps the base install light).
- **`gnn` as the second reference baseline.** `gnn`'s v0.5 milestone
  has been waiting for a pinned dataset registry; pm-bench provides
  it the moment any single dataset is pinned.
- **Alignment-based conformance** behind a `[discovery]` extra
  (PM4Py petri-net replay). The DFG fitness × precision baseline
  ships today; alignment-based replay is the principled v0.6+
  upgrade.

## Known gaps

- **No real BPI data on the leaderboard yet.** `synthetic-toy` is the
  only verified dataset until a contributor does the one-time TOS
  fetch and lands the registry pin PR.
- **`gnn` cross-repo integration is pending.** Sibling repo's v0.5
  milestone is gated on a pinned pm-bench dataset.
- **Six lower-priority audit items deferred** (see
  `git log --grep "deferred"`): a few cosmetic schema tightenings
  and one documentation polish item.
