# Standings

_Auto-generated from `leaderboard/<task>/<dataset>.json` — regenerate with `pm-bench leaderboard --all --markdown > STANDINGS.md`._

### bottleneck · synthetic-toy
_NDCG@10 over per-transition wait times (higher is better)_

| Model | NDCG@k | k | n_transitions |
|---|---:|---:|---:|
| `mean-wait-ref` | 0.9786 | 10 | 6 |

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
