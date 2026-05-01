# Goals

## North star
Be the default benchmark for new process-mining methods. Within 18
months, ≥10 external papers report `pm-bench` numbers in their abstract.

## v0 success criteria

- [x] **End-to-end loop runs on `synthetic-toy`** — split → prefixes →
  predict → score, covered by `tests/test_e2e.py`. **Done.**
- [x] **5 tasks with fixed scoring scripts** — next-event,
  remaining-time, outcome, bottleneck, conformance. Each ships with a
  CPython reference baseline AND a floor baseline (every leaderboard
  board has ≥2 entries). **Done.**
- [x] **Leaderboard with drift detection** — JSON Schema-validated
  standings, `pm-bench leaderboard --all --verify` walks every board
  and exits non-zero on any drift; STANDINGS.md auto-regenerated and
  staleness is a CI failure. **Done.**
- [🟡] **7 datasets fetchable + hash-verified** — fetch/hash/cache
  machinery shipped (`pm-bench fetch <name> [--pin]`, atomic +
  concurrent-safe download, sha256 verification); per-dataset hash
  pins pending the one-time TOS-gated 4TU/Mendeley downloads. **One
  human step away.**
- [ ] **`gnn` runs end-to-end as the reference baseline.** Markov is
  the in-tree reference today; gnn integration unblocks the moment a
  real BPI dataset is pinned. **v0.5.**

## v0 quality bar (added during the audit cascade — non-negotiable)

- **Determinism**: every reference number stable across runs +
  `PYTHONHASHSEED`s. CSV writers produce byte-identical output.
- **Atomic I/O**: every CSV/JSON writer stages PID+UUID-suffixed
  tmp file and `Path.replace`s on success; cleanup on failure.
- **Concurrency-safe**: parallel `pm-bench fetch` of the same dataset
  cannot corrupt the cache.
- **No raw tracebacks** in any user-facing CLI path. Every verb exits
  cleanly with a type-prefixed error message.
- **Schema-validated submissions**: model name regex, predictions_path
  rejects abs / `..` / empty, score values must be numeric, scored_at
  must be ISO 8601 with time component, no duplicate model names.
- **Round-trip safe**: BOM-tolerant reads, utf-8 writes, whitespace
  stripped on every column, empty / pipe-bearing activities rejected
  on write, NaN / Inf rejected on write AND score.
- **229 tests** covering correctness, drift detection, schema
  validation, concurrency, and every error path.

## Leaderboard

- Standings JSON format with reference + floor baselines on every of
  the 5 task/synthetic-toy pairs ✅
- JSON Schema validator (`pm-bench validate <board.json>`) ✅
- `pm-bench leaderboard [--all] [--verify] [--markdown]` ✅
- `pm-bench compare A.json B.json` with direction annotations ✅
- `.github/workflows/leaderboard.yml` runs `--all --verify` on every
  PR/push that touches scoring code or standings ✅
- STANDINGS.md auto-generated; staleness is a CI failure ✅
- Remaining: URL-fetch submission flow (predictions hosted offsite)
  is a v1.x ergonomics nice-to-have, not a v0 blocker.

## v1 success criteria
- ≥3 external groups submit to the leaderboard
- Cited in ≥5 papers
- BPI Challenge hosts (TU/e) acknowledge or link

## Architecture decisions
- Python 3.10+, `pip install pm-bench`
- Datasets NOT in the repo — fetched from canonical 4TU URLs and cached
- Splits are deterministic case-chrono with case_id tiebreaker
- Scoring is pure CPython, no GPU dep
- One shared `_open_text` opener (gz-aware, BOM-stripping, atomic
  writes); divergence between CLI and rescore paths is impossible by
  construction
- Schema validation is stdlib-only (no `jsonschema` dep)

## Non-goals
- Hosting the datasets ourselves (legal complexity)
- Inventing new tasks; we curate, we don't speculate
- Becoming a model zoo (that's `gnn`)

## Out of scope (for now)
- Streaming / online evaluation
- Multi-perspective conformance (resource, data attributes)
- Any non-BPI-style task
