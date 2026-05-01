# Goals

## North star
Be the default benchmark for new process-mining methods. Within 18 months,
≥10 external papers report `pm-bench` numbers in their abstract.

## v0 success criteria
- 7 datasets fetchable + hash-verified — fetch/hash machinery shipped
  (`pm-bench fetch <name> [--pin]`); per-dataset hash pins pending
  the one-time TOS-gated downloads
- 5 tasks with fixed scoring scripts (next-event ✅, remaining-time ✅,
  outcome ✅; conformance, bottleneck pending)
- `gnn` runs end-to-end as the reference baseline (Markov reference ✅;
  `gnn` integration pending the first pinned dataset)
- End-to-end loop runs on `synthetic-toy` ✅ — split → prefixes →
  predict → score, covered by `tests/test_e2e.py`

## Leaderboard
- Standings JSON format and reference Markov entry on `synthetic-toy`
  shipped (`leaderboard/next-event/synthetic-toy.json`)
- `pm-bench leaderboard --verify` re-scores entries to catch drift; a
  test guards the Markov-ref score
- CI workflow shipped: `.github/workflows/leaderboard.yml` runs
  `pm-bench leaderboard --all --verify` on every PR / push that
  touches scoring code or standings files
- Remaining: static landing page (HTML / index page on a tag) and the
  URL-fetch submission flow for entries whose predictions live offsite

## v1 success criteria
- ≥3 external groups submit to the leaderboard
- Cited in ≥5 papers
- BPI Challenge hosts (TU/e) acknowledge or link

## Architecture decisions
- Python 3.10+, `pip install pm-bench`
- Datasets NOT in the repo — fetched from canonical 4TU URLs and cached
- Splits are deterministic functions of `(dataset_hash, task, seed)`
- Scoring is pure CPython, no GPU dep

## Non-goals
- Hosting the datasets ourselves (legal complexity)
- Inventing new tasks; we curate, we don't speculate
- Becoming a model zoo (that's `gnn`)

## Out of scope (for now)
- Streaming / online evaluation
- Multi-perspective conformance (resource, data attributes)
- Any non-BPI-style task
