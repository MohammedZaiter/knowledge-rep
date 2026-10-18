# model/

Learning over our graph: one node classification model and one link
prediction model, each next to a simple baseline, with a split that does not
leak and several seeds.

```sh
python pipeline/run.py --no-load        # writes build/graph.nt
pip install -r model/requirements.txt   # CPU is enough
python model/run_all.py                 # every script below -> model/results/
```

`run_all.py` saves each script's output in `model/results/<script>.txt` and
writes `run-metadata.json` with the date, the package versions and a hash of
the graph it read. The numbers in the report come only from these files.

| Script | What it does |
|---|---|
| `build_graph.py` | converts `build/graph.nt` into a PyTorch Geometric graph (foods, categories, nutrients) |
| `baseline.py` | logistic regression on the same features: the table baseline |
| `gnn.py` | GraphSAGE node classification |
| `link_prediction.py` | TransE against a popularity count |
| `learning_utils.py` | the splits and the ranking scores |

## Node classification: is a food high in fat?

The label is fat above 20 g per 100 g: 55 high-fat foods of 348; the 10 foods
with no fat value are left out rather than guessed. The features are the
other five nutrients (log amount and a missing flag each).

**What we removed from the features, and why:** the fat amount itself, because
the label is computed from it. `baseline.py` keeps it once, on purpose, to
show the leak: PR-AUC 1.000 on a random split.

**The split:** by USDA category. About 30% of the 18 categories go to the test
set with all their foods, so the model cannot pass the test by remembering a
category. We also report a random split, but never only that one.

**Why not a split by time:** our foods do have a date, `publication_date`
(11 USDA release dates from 2019-04-01 to 2024-04-18). It is the day USDA
published the analysis, not the time of an event, and the label (how much fat
a food contains) does not change with it: a food released in 2024 is not "the
future" of one released in 2019. A split by date would also leak: cut at
2023-01-01, all 77 foods published from 2023 fall in one of the 9 categories
that already have earlier foods in training, which is exactly the
remembering that the category split prevents.

**Result** (PR-AUC, category split; guessing scores 0.158):

| Model | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | mean of 4 |
|---|---|---|---|---|---|---|
| logistic regression | 0.163 | 0.523 | — | 0.129 | 0.754 | 0.392 |
| GraphSAGE | 0.163 | 0.867 | — | 0.090 | 0.641 | 0.440 |

Seed 2 puts no high-fat food in the test set, so there is nothing to score.
The spread between seeds (0.090 to 0.867 for GraphSAGE) is larger than the
gap between the two models, so we do not claim that GraphSAGE is better.
Only 7 of the 18 categories have any high-fat food.

## Link prediction: which category does a food belong to?

We hide category-to-food links and rank the true category among all 18
(filtered ranking), three seeds:

| Model | seed 0 | seed 1 | seed 2 | mean MRR |
|---|---|---|---|---|
| TransE | 0.382 | 0.345 | 0.289 | 0.339 |
| popularity (most common category) | 0.395 | 0.423 | 0.527 | 0.448 |

TransE loses to the popularity baseline on every seed. We report it as it
is: with 18 categories and few links per food, the count of the largest
categories is hard to beat.
