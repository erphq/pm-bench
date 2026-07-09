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


def test_markov_empty_prefix_falls_back_to_unigram() -> None:
    # prefix=() means last=None, so rank() must use the unigram, not transitions.
    model = fit_markov(_events(), ["c1", "c2"])
    targets = [Prefix(case_id="c3", prefix_idx=0, prefix=(), true_next="a")]
    preds = predict_markov(model, targets)
    # c1 and c2 each have {a, b, c}: unigram has three distinct activities.
    assert set(preds[0].ranked) == {"a", "b", "c"}


def test_markov_multiple_successors_ranked_by_frequency() -> None:
    # "a→b" appears 3 times, "a→c" appears 1 time: "b" must rank before "c".
    base = dt.datetime(2024, 1, 1)
    events = [
        ("x1", "a", base),
        ("x1", "b", base + dt.timedelta(hours=1)),
        ("x2", "a", base),
        ("x2", "b", base + dt.timedelta(hours=1)),
        ("x3", "a", base),
        ("x3", "b", base + dt.timedelta(hours=1)),
        ("x4", "a", base),
        ("x4", "c", base + dt.timedelta(hours=1)),
    ]
    model = fit_markov(events, ["x1", "x2", "x3", "x4"])
    targets = [Prefix(case_id="x1", prefix_idx=1, prefix=("a",), true_next="b")]
    preds = predict_markov(model, targets)
    ranked = list(preds[0].ranked)
    assert ranked[0] == "b"
    assert ranked.index("b") < ranked.index("c")


def test_markov_empty_train_set_gives_empty_ranking() -> None:
    # No training cases: both transitions and unigram are empty.
    # rank() returns [] which predict_markov wraps as an empty tuple.
    model = fit_markov(_events(), [])
    targets = [Prefix(case_id="c3", prefix_idx=1, prefix=("a",), true_next="b")]
    preds = predict_markov(model, targets)
    assert len(preds[0].ranked) == 0
