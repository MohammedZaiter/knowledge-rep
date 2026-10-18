# Model layer: course Session 6

The algorithms come from `build_graph.py`, `baseline.py`, `gnn.py`, `learning_utils.py` and `link_prediction.py` in Session 6. Source hashes are in `../COURSE_CODE_SOURCES.json`.

## Classification

Predict whether a food has more than 20 g fat per 100 g. There are 348 labelled foods, 55 positives; 10 foods with missing fat observations are excluded.

- Predictors: log1p protein, carbohydrate, fiber, sodium and sugars; five availability flags. Numerical zero with an unavailable flag is a model encoding, not an imputed source observation.
- Label leakage removed: fat amount is not a feature. The full observation graph, identifiers and names are not model inputs. Fat is retained separately only for the intentional leak demonstration.
- Graph: food/category HeteroData, category identity features, reverse edges via the demo's ToUndirected transform. No class labels are fed into message passing.
- Splits: the course stratified random split plus five category-held-out splits; no category occurs on both sides. This is a transductive graph experiment, not a fully inductive deployment benchmark.
- Baseline: course balanced logistic regression, train-fitted one-hot categories.
- GNN: course two-layer GraphSAGE, hidden 32, 100 epochs, Adam 0.01, weighted binary loss; three random-split training seeds and five group-split seeds.

Seed 2 has no positive test examples. Its PR-AUC is unscoreable and explicitly recorded, rather than substituted with a favorable number. The reported mean/spread uses the other four group seeds. Publication dates are snapshot metadata; category grouping tests transfer to different food groups rather than forecasting future foods.

## Link prediction

The exact course TransE/popularity evaluation is adapted from plant/product links to category/food membership. Hide 10% test and 10% validation membership links. Side information is observed food/nutrient links; inverse category facts are withheld. TransE uses dimension 32, 150 epochs and three seeds. Report filtered MRR/Hits@1; cold test entities are excluded and counted by the original course procedure. The held-out graph retains observed nutrient-presence facts, so it is a transductive task.

## Run and inspect

From the repository root: `python model/run_learning.py` after mapping. Generated datasets/logs are in `build/learning/`. Reviewed snapshots, package versions and input hashes are in `model/results/`. These are experiments; the UI does not use model predictions as food or medical advice.
