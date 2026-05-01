"""Reference baselines that ship with pm-bench.

Baselines exist to anchor the leaderboard: a submission that loses to
the markov reference is an immediate red flag. They're deliberately
simple — no torch, no scikit-learn, no GPUs, just CPython — so anyone
can read the code and trust the number.
"""
from __future__ import annotations

from pm_bench.baselines.markov import MarkovBaseline, predict_markov

__all__ = ["MarkovBaseline", "predict_markov"]
