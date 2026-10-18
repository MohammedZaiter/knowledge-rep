"""Does tie handling change the popularity baseline's score?

    python model/tie_check.py

link_prediction.py ranks with a stable sort, so categories with the same
popularity count keep their alphabetical order. Sun et al. (ACL 2020) showed
that how ties are broken can change link prediction scores. This script
rebuilds the same three splits and scores the popularity baseline with ties
broken as in the run, optimistically (the true category first), pessimistically
(last), and by the mean rank of the tied group.
"""

import collections
from pathlib import Path

import numpy as np
import torch
from learning_utils import mrr

HERE = Path(__file__).resolve().parent
SEEDS = range(3)


def main():
    b = torch.load(
        HERE.parent / "build" / "learning" / "food-graph.pt", weights_only=False
    )
    contains, other = b["category_links"], b["side_links"]
    categories = sorted({h for h, _, _ in contains})
    known = collections.defaultdict(set)
    for h, _, t in contains:
        known[t].add(h)
    side = {x for h, _, t in other for x in (h, t)}
    print(
        "popularity baseline MRR under four tie rules (same splits as link_prediction.py)"
    )
    for seed in SEEDS:
        rng = np.random.RandomState(seed)
        perm = rng.permutation(len(contains))
        n = len(contains) // 10
        test = [contains[i] for i in perm[:n]]
        train = [contains[i] for i in perm[2 * n :]]
        seen = side | {x for h, _, t in train for x in (h, t)}
        test = [x for x in test if x[0] in seen and x[2] in seen]
        pop = collections.Counter(h for h, _, _ in train)
        as_run, best, worst, middle, tied = [], [], [], [], 0
        for h, _, t in test:
            cand = [p for p in categories if p == h or p not in known[t]]
            s = pop.get(h, 0)
            above = sum(pop.get(p, 0) > s for p in cand)
            same = sum(pop.get(p, 0) == s for p in cand)
            tied += same > 1
            as_run.append(sorted(cand, key=lambda p: -pop.get(p, 0)).index(h) + 1)
            best.append(above + 1)
            worst.append(above + same)
            middle.append(above + (same + 1) / 2)
        print(
            f"seed {seed}: {len(test)} links, {tied} with a tie  "
            f"as run {mrr(as_run):.3f}  optimistic {mrr(best):.3f}  "
            f"pessimistic {mrr(worst):.3f}  mean rank {mrr(middle):.3f}"
        )


if __name__ == "__main__":
    main()
