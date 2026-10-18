# ruff: noqa: E402, E731
"""Course Session 6 link_prediction.py: TransE versus popularity, three seeds, 150 epochs and filtered head ranking. FoodScope hides category-contains-food links; observed nutrient links are side information. Inverse category links are excluded."""

import collections
import os
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
# PyKEEN uses PyStow for its cache.  Keep that cache with the generated lab
# data instead of assuming every student can write to a home-directory default
# such as ~/.data (often false on managed lab computers).
os.environ.setdefault("PYSTOW_HOME", str(HERE.parent / "build" / "learning" / "pystow"))

from learning_utils import mrr
from pykeen.pipeline import pipeline
from pykeen.triples import TriplesFactory

SEEDS = range(3)


def triples(b):
    # Course target/side-triple split; only the food relation vocabulary changes.
    return b["category_links"], b["side_links"]


def ranks_among_categories(score, test, known, categories):
    """Rank the true category among all categories, filtered; returns one rank per test link."""
    out = []
    for h, _, t in test:
        cand = [p for p in categories if p == h or p not in known[t]]
        order = sorted(cand, key=lambda p: -score(p, t))
        out.append(order.index(h) + 1)
    return out


def main():
    b = torch.load(
        HERE.parent / "build" / "learning" / "food-graph.pt", weights_only=False
    )
    contains, other = triples(b)
    categories = sorted({h for h, _, _ in contains})
    known = collections.defaultdict(set)
    for h, _, t in contains:
        known[t].add(h)
    print(
        f"{len(contains):,} contains links ({len(categories)} categories), {len(other):,} other links"
    )
    for seed in SEEDS:
        rng = np.random.RandomState(seed)
        perm = rng.permutation(len(contains))
        n = len(contains) // 10
        test, valid, train = (
            [contains[i] for i in perm[:n]],
            [contains[i] for i in perm[n : 2 * n]],
            [contains[i] for i in perm[2 * n :]],
        )
        tf = TriplesFactory.from_labeled_triples(np.array(train + other))
        seen = lambda L: [
            x for x in L if x[0] in tf.entity_to_id and x[2] in tf.entity_to_id
        ]
        cold = len(test) - len(seen(test))
        test, valid = seen(test), seen(valid)
        mk = lambda L: TriplesFactory.from_labeled_triples(
            np.array(L), entity_to_id=tf.entity_to_id, relation_to_id=tf.relation_to_id
        )
        result = pipeline(
            training=tf,
            validation=mk(valid),
            testing=mk(test),
            model="TransE",
            model_kwargs=dict(embedding_dim=32),
            training_kwargs=dict(num_epochs=150, batch_size=512),
            random_seed=seed,
            device="cpu",
            use_tqdm=False,
        )
        model, ent, rel = result.model, tf.entity_to_id, tf.relation_to_id["contains"]
        with torch.no_grad():
            cache = {}

            def transe(p, t):
                if t not in cache:
                    cache[t] = model.score_h(torch.tensor([[rel, ent[t]]]))[0]
                return (
                    float(cache[t][ent[p]]) if p in ent else float("-inf")
                )  # a category never seen in training ranks last

            r_model = ranks_among_categories(transe, test, known, categories)
        popular = collections.Counter(h for h, _, _ in train)
        r_pop = ranks_among_categories(
            lambda p, t: popular.get(p, 0), test, known, categories
        )
        hits1 = lambda r: float(np.mean(np.asarray(r) == 1))
        print(
            f"seed {seed}: {len(test)} hidden links scored ({cold} left out: their food appears in no other link)"
        )
        print(f"  TransE      MRR {mrr(r_model):.3f}  Hits@1 {hits1(r_model):.3f}")
        print(f"  popularity  MRR {mrr(r_pop):.3f}  Hits@1 {hits1(r_pop):.3f}")


if __name__ == "__main__":
    main()
