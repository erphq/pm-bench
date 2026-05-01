# Standings

_Auto-generated from `leaderboard/<task>/<dataset>.json` - regenerate with `pm-bench leaderboard --all --markdown > STANDINGS.md`._

### bottleneck · synthetic-toy
_NDCG@10 over per-transition wait times (higher is better)_

| Model | NDCG@k | k | n_transitions |
|---|---:|---:|---:|
| `mean-wait-ref` | 0.9786 | 10 | 6 |

### conformance · synthetic-toy
_DFG fitness × precision → F-score (higher is better)_

| Model | F | Fitness | Precision | n_test | n_model |
|---|---:|---:|---:|---:|---:|
| `dfg-ref` | 0.8571 | 1.0000 | 0.7500 | 6 | 8 |

### next-event · synthetic-toy
_top1 / top3 accuracy_

| Model | top1 | top3 | n |
|---|---:|---:|---:|
| `markov-ref` | 0.9756 | 1.0000 | 41 |

### remaining-time · synthetic-toy
_MAE in days (lower is better)_

| Model | mae_days | n |
|---|---:|---:|
| `mean-ref` | 1.2546 | 41 |
