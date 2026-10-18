"""Course Session 6 build_graph.py adapted to FoodScope. Builds HeteroData for high-fat classification, excluding fat from predictors, and stores category/nutrient triples for the course link-prediction experiment."""

import sys
import time
from pathlib import Path

import numpy as np
import torch
from rdflib import RDF, Graph, Namespace
from torch_geometric.data import HeteroData

HERE = Path(__file__).resolve().parent
SOURCES = [HERE.parent / "build" / "graph.nt"]
OUT = HERE.parent / "build" / "learning" / "food-graph.pt"
UL = Namespace("https://ul.edu.lb/kr/food#")
TARGET_NUTRIENT = "https://ul.edu.lb/kr/id/nutrient/usda/1004"
# Same demo structure: features per node kind and typed edge_index lists.
# Food adaptation: high-fat (>20 g/100 g) is the withheld target; category is the split group.
FEATURE_NUTRIENTS = ["1003", "1005", "1079", "1093", "2000"]


def main():
    src = next((p for p in SOURCES if p.exists()), None)
    if src is None:
        sys.exit("No mapped food graph. Run python pipeline/run.py --no-load first.")
    t0 = time.time()
    g = Graph().parse(src, format="nt")
    all_foods = sorted(set(g.subjects(RDF.type, UL.Food)), key=str)
    amounts = {}
    for food in all_foods:
        amounts[food] = {
            str(g.value(o, UL.nutrient)).rsplit("/", 1)[-1]: float(
                g.value(o, UL.amount)
            )
            for o in g.objects(food, UL.hasObservation)
        }
    # Missing labels are excluded rather than called negative.
    foods = [food for food in all_foods if "1004" in amounts[food]]
    y = np.array([int(amounts[food]["1004"] > 20) for food in foods])
    ids = {"food": {food: i for i, food in enumerate(foods)}}

    def node(kind, iri):
        table = ids.setdefault(kind, {})
        return table.setdefault(iri, len(table))

    pairs = [
        (ids["food"][food], node("category", g.value(food, UL.category)))
        for food in foods
    ]
    # No target amounts, observation IDs, food names/IDs, or target classes in features.
    # Zero with an explicit missingness flag represents unavailable predictors, not a source fact.
    x = np.array(
        [
            [np.log1p(amounts[food].get(n, 0)) for n in FEATURE_NUTRIENTS]
            + [float(n in amounts[food]) for n in FEATURE_NUTRIENTS]
            for food in foods
        ]
    )
    data = HeteroData()
    data["food"].x = torch.tensor(x, dtype=torch.float)
    data["category"].x = torch.eye(len(ids["category"]))
    data["food", "category", "category"].edge_index = torch.tensor(
        np.array(pairs).T, dtype=torch.long
    ).contiguous()
    # Link-prediction adaptation: hide category->food membership; side links are observed nutrients.
    # No inverse category edge is supplied as an answer-revealing feature.
    category_links = [
        (str(g.value(food, UL.category)), "contains", str(food)) for food in all_foods
    ]
    side_links = sorted(
        {
            (str(food), "hasNutrient", str(g.value(o, UL.nutrient)))
            for food in all_foods
            for o in g.objects(food, UL.hasObservation)
        }
    )
    extra = {
        "y": torch.tensor(y),
        "fat_amount": torch.tensor([amounts[food]["1004"] for food in foods]),
        "category": torch.tensor(
            [ids["category"][g.value(food, UL.category)] for food in foods]
        ),
        "food_iri": [str(food) for food in foods],
        "names": {k: [str(i) for i in t] for k, t in ids.items() if k != "food"},
        "source": src.name,
        "category_links": category_links,
        "side_links": side_links,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"data": data, **extra}, OUT)
    print(f"read {src.name}: {len(g):,} triples in {time.time() - t0:.1f} s")
    print(
        f"label: {int(y.sum())} high-fat foods of {len(y)}; {len(all_foods) - len(foods)} missing labels excluded"
    )
    print(
        f"features: {FEATURE_NUTRIENTS}, log1p amounts and missingness; fat amount retained only for leak demonstration"
    )
    print(
        f"split groups: {len(ids['category'])} USDA categories; source: {src.name}; written: {OUT}"
    )


if __name__ == "__main__":
    main()
