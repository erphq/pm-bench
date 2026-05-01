import datetime as dt

from pm_bench import Prefix
from pm_bench.baselines.markov import fit_markov, predict_markov


def _events() -> list[tuple[str, str, dt.datetime]]:
    base = dt.datetime(2024, 1, 1)
    return [
        # Train: c1, c2 - pattern "a→b" 2x, "b→c" 2x.
        ("c1", "a", base),
        ("c1", "b", base + dt.timedelta(hours=1)),
        ("c1", "c", base + dt.timedelta(hours=2)),
        ("c2", "a", base),
        ("c2", "b", base + dt.timedelta(hours=1)),
        ("c2", "c", base + dt.timedelta(hours=2)),
        # Test: c3 - same shape.
        ("c3", "a", base),
        ("c3", "b", base + dt.timedelta(hours=1)),
        ("c3", "c", base + dt.timedelta(hours=2)),
    ]


def test_markov_top1_perfect_on_deterministic_chain() -> None:
    model = fit_markov(_events(), ["c1", "c2"])
    targets = [
        Prefix(case_id="c3", prefix_idx=1, prefix=("a",), true_next="b"),
        Prefix(case_id="c3", prefix_idx=2, prefix=("a", "b"), true_next="c"),
    ]
    preds = predict_markov(model, targets)
    assert preds[0].ranked[0] == "b"
    assert preds[1].ranked[0] == "c"


def test_markov_falls_back_to_unigram_for_unseen_last() -> None:
    model = fit_markov(_events(), ["c1", "c2"])
    targets = [Prefix(case_id="c3", prefix_idx=1, prefix=("never_seen",), true_next="b")]
    preds = predict_markov(model, targets)
    # Unigram is non-empty and ranked; just assert we got *some* ranked list.
    assert len(preds[0].ranked) > 0
