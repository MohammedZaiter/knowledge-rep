"""Course Session 6 split and ranking helpers. Only domain names change: category replaces customer and food replaces order."""

import numpy as np


# ---------------------------------------------------------------- splits
def split_random(n_foods, y, test_share=0.3, seed=0):
    """Put a random 30% of the foods in the test set, with the same share of
    high-fat foods on both sides (a "stratified" split). Returns (train, test),
    two arrays of order positions."""
    rng = np.random.RandomState(seed)
    test = []
    for label in (0, 1):
        idx = np.flatnonzero(y == label)
        rng.shuffle(idx)
        test.extend(idx[: int(round(test_share * len(idx)))])
    test = np.sort(np.array(test))
    train = np.setdiff1d(np.arange(n_foods), test)
    return train, test


def split_by_category(category, test_share=0.3, seed=0):
    """Put about 30% of the CATEGORIES in the test set, with all their foods.
    No category has foods on both sides, so a model cannot pass the test by
    remembering categorys. Returns (train, test), arrays of order positions."""
    rng = np.random.RandomState(seed)
    groups = np.unique(category)
    rng.shuffle(groups)
    test_groups = groups[: int(round(test_share * len(groups)))]
    test = np.flatnonzero(np.isin(category, test_groups))
    train = np.flatnonzero(~np.isin(category, test_groups))
    return train, test


# ---------------------------------------------------------------- scores
def precision_at_k(y_true, scores, k=100):
    """Of the k foods the model ranks most at risk, the share that were high-fat."""
    top = np.argsort(-np.asarray(scores), kind="stable")[:k]
    return float(np.asarray(y_true)[top].mean())


def mrr(ranks):
    """Mean reciprocal rank: the average of 1/rank of the right answer.
    Rank 1 counts 1, rank 2 counts 0.5, rank 10 counts 0.1."""
    return float(np.mean(1.0 / np.asarray(ranks, dtype=float)))
