# Status

_Last updated: 2026-04-30._

## Where we are

Pre-v0. The end-to-end loop runs on the bundled `synthetic-toy`
dataset; the seven public datasets are still pending v0.1's fetch +
hash machinery.

A submission today looks like:

```bash
pm-bench split synthetic-toy > split.json
pm-bench prefixes synthetic-toy --split split.json --out prefixes.csv
pm-bench predict synthetic-toy --split split.json \
  --prefixes prefixes.csv --out predictions.csv --baseline markov
pm-bench score predictions.csv --prefixes prefixes.csv --task next-event
# → top1 0.976, top3 1.000 (Markov on synthetic-toy)
```

That sequence is the contract — it's what `tests/test_e2e.py` runs in
CI, and it's what the leaderboard CI will run once datasets are pinned.

## Recently shipped

- **End-to-end loop on synthetic-toy** (`end-to-end-loop` branch).
  - `pm_bench/prefixes.py` — extract prediction targets from a split,
    write/read CSV. Skips length-1 cases.
  - `pm_bench/predictions.py` — predictions CSV format
    (`case_id,prefix_idx,predictions`).
  - `pm_bench/baselines/markov.py` — first-order Markov reference
    baseline. Trained on the train partition only; falls back to
    unigram for unseen last-activities.
  - CLI gained `prefixes`, `predict`, `score`. The full
    `split → prefixes → predict → score` loop now matches what the
    README advertises.
  - `tests/test_e2e.py` covers the loop end-to-end via the click
    runner; format changes will trip it.
- **v0.0** (initial release): scaffold, registry, case-chrono split,
  next-event scoring function, CLI `list` / `info` / `split`.

## Next up

- **v0.1 — dataset fetch + hash** for the seven public logs. The 4TU
  portal needs interactive TOS acceptance per dataset, so the fetch
  itself is a one-time manual step; the rest (cache → verify hash →
  parse XES → run the same loop) is automated. This is the work that
  unblocks every downstream milestone.
- **`gnn` as the second reference baseline** once v0.1 lands. `gnn`'s
  v0.5 milestone is symmetrical with this — it's been waiting for a
  pinned dataset registry, which `pm-bench` is meant to provide.
- Additional tasks beyond next-event (remaining-time, outcome,
  conformance, bottleneck). The split + prefixes machinery is shared;
  scoring is the per-task piece.

## Known gaps

- No `pm-bench fetch` yet. README still hints at it; the install &
  use section now shows the loop that actually works (synthetic-toy
  only) so the doc and the CLI line up.
- `predict` currently only knows `markov`. The `--baseline` flag is a
  click choice so adding a second is a one-liner, but the second one
  worth adding is `gnn`, which depends on v0.1.
