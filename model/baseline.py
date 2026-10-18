"""Course Session 6 baseline.py: unchanged logistic-regression algorithm. FoodScope inputs are log1p non-fat nutrient amounts, missingness flags and category one-hot features. Compare the intentional fat leak, random split and five category-held-out seeds."""

from pathlib import Path

import numpy as np
import torch
from learning_utils import precision_at_k, split_by_category, split_random
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, roc_auc_score
from sklearn.preprocessing import OneHotEncoder

HERE = Path(__file__).resolve().parent
SEEDS = range(5)


def load():
    b = torch.load(
        HERE.parent / "build" / "learning" / "food-graph.pt", weights_only=False
    )
    ids = np.column_stack([b["category"]])
    return (
        b["data"]["food"].x.numpy(),
        ids,
        b["fat_amount"].numpy(),
        b["y"].numpy(),
        b["category"].numpy(),
    )


def fit_score(x, ids, y, train, test, extra=None):
    onehot = OneHotEncoder(handle_unknown="ignore").fit(ids[train])

    def rows(i):
        parts = [onehot.transform(ids[i]).toarray(), x[i]]
        return np.hstack(parts + ([extra[i, None]] if extra is not None else []))

    model = LogisticRegression(max_iter=2000, class_weight="balanced").fit(
        rows(train), y[train]
    )
    p = model.predict_proba(rows(test))[:, 1]
    yt = y[test]
    return {
        "positive in test": int(yt.sum()),
        "PR-AUC": average_precision_score(yt, p) if yt.sum() else float("nan"),
        "ROC-AUC": roc_auc_score(yt, p) if 0 < yt.sum() < len(yt) else float("nan"),
        "precision@100": precision_at_k(yt, p, 100),
        "accuracy": accuracy_score(yt, p > 0.5),
    }


def line(name, r):
    if r["positive in test"] == 0:
        return f"{name:<34} positive in test   0  no high-fat food in the test set: nothing to measure"
    return (
        f"{name:<34} positive in test {r['positive in test']:>3}  PR-AUC {r['PR-AUC']:.3f}  ROC-AUC {r['ROC-AUC']:.3f}  "
        f"precision@100 {r['precision@100']:.2f}  accuracy {r['accuracy']:.3f}"
    )


def main():
    x, ids, fat_amount, y, category = load()
    print(
        f"{len(y):,} foods, {int(y.sum())} high-fat ({y.mean():.1%}). Guessing scores PR-AUC {y.mean():.3f}; "
        f'"never high-fat" scores accuracy {1 - y.mean():.3f}.\n'
    )
    train, test = split_random(len(y), y)
    print(
        line(
            "1 · random split, fat amount kept",
            fit_score(x, ids, y, train, test, extra=fat_amount),
        )
    )
    print(line("2 · random split", fit_score(x, ids, y, train, test)))
    for s in SEEDS:
        train, test = split_by_category(category, seed=s)
        print(
            line(f"3 · split by category, seed {s}", fit_score(x, ids, y, train, test))
        )
    positive_categories = np.unique(category[y == 1])
    print(
        f"\nOnly {len(positive_categories)} of {len(np.unique(category))} categories ever have a high-fat food. "
        "Group splits keep entire categories out of training; per-seed scores below describe the variation."
    )


if __name__ == "__main__":
    main()
