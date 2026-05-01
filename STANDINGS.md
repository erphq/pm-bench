# Standings

_Auto-generated from `leaderboard/<task>/<dataset>.json` - regenerate with `pm-bench leaderboard --all --markdown > STANDINGS.md`._

### bottleneck · synthetic-toy
_NDCG@10 over per-transition wait times (higher is better)_

| Model | NDCG@k | k | n_transitions |
|---|---:|---:|---:|
| `mean-wait-ref` | 0.9911 | 10 | 9 |

### conformance · synthetic-toy
_DFG fitness × precision → F-score (higher is better)_

| Model | F | Fitness | Precision | n_test | n_model |
|---|---:|---:|---:|---:|---:|
| `dfg-ref` | 1.0000 | 1.0000 | 1.0000 | 9 | 9 |
| `empty-ref` | 0.0000 | 0.0000 | 0.0000 | 9 | 0 |

### next-event · synthetic-toy
_top1 / top3 accuracy_

| Model | top1 | top3 | n |
|---|---:|---:|---:|
| `markov-ref` | 0.9304 | 1.0000 | 158 |
| `uniform-ref` | 0.2025 | 0.2785 | 158 |

### outcome · synthetic-toy
_ROC AUC (higher is better)_

| Model | AUC | n | n_pos |
|---|---:|---:|---:|
| `prior-ref` | 0.6319 | 158 | 45 |

### remaining-time · synthetic-toy
_MAE in days (lower is better)_

| Model | mae_days | n |
|---|---:|---:|
| `mean-ref` | 1.3481 | 158 |
| `zero-ref` | 2.7410 | 158 |
