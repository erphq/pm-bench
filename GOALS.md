# Goals

## North star
Be the default benchmark for new process-mining methods. Within 18 months,
≥10 external papers report `pm-bench` numbers in their abstract.

## v0 success criteria
- 7 datasets fetchable + hash-verified
- 5 tasks with fixed scoring scripts
- `gnn` runs end-to-end as the reference baseline

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
