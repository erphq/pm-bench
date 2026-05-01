# Status

_Last updated: 2026-04-30._

## Where we are

Pre-v0. Two pieces shipped on top of v0.0:

1. The end-to-end loop runs on the bundled `synthetic-toy` dataset
   (split → prefixes → predict → score; Markov reference baseline
   gets top-1 0.976, top-3 1.000).
2. The fetch + hash + cache machinery is in place. `pm-bench fetch
   <name>` resolves a dataset to a local path, verifies the registry
   sha256, and prints precise instructions for the TOS-gated download
   step on 4TU / Mendeley. `--pin` emits the `registry.yml` patch a
   contributor pastes into a PR after the manual download.

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
