"""Course Session 6 gnn.py: GraphSAGE, to_hetero, two layers, 32 hidden units, 100 epochs and the same Adam/BCE training loop. FoodScope uses food/category nodes and the baseline category splits."""

from pathlib import Path

import numpy as np
import torch
import torch_geometric.transforms as T
from baseline import line
from learning_utils import precision_at_k, split_by_category, split_random
from sklearn.metrics import average_precision_score, roc_auc_score
from torch_geometric.nn import SAGEConv, to_hetero

HERE = Path(__file__).resolve().parent
EPOCHS, HIDDEN = 100, 32


class SAGE(torch.nn.Module):
    """Two GraphSAGE layers and a score. (-1, -1): input sizes are read from the data."""

    def __init__(self):
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), HIDDEN)
        self.conv2 = SAGEConv((-1, -1), HIDDEN)
        self.score = torch.nn.Linear(HIDDEN, 1)

    def forward(self, x, edge_index):  # the name edge_index matters to to_hetero
        h = self.conv1(x, edge_index).relu()
        h = self.conv2(h, edge_index).relu()
        return self.score(h)


def run(data, y, train, test, seed=0):
    if len(np.unique(y[train])) < 2:
        raise ValueError(
            "Training split has only one class; cannot train the course classifier"
        )
    torch.manual_seed(seed)
    model = to_hetero(SAGE(), data.metadata(), aggr="sum")
    model(data.x_dict, data.edge_index_dict)  # one pass to size the layers
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    target = torch.tensor(y, dtype=torch.float)
    weight = torch.tensor(
        (1 - y[train].mean()) / y[train].mean()
    )  # high-fat foods are rare: count them more
    for _ in range(EPOCHS):
        model.train()
        opt.zero_grad()
        out = model(data.x_dict, data.edge_index_dict)["food"].squeeze()
        torch.nn.functional.binary_cross_entropy_with_logits(
            out[train], target[train], pos_weight=weight
        ).backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        p = torch.sigmoid(
            model(data.x_dict, data.edge_index_dict)["food"].squeeze()
        ).numpy()[test]
    yt = y[test]
    return {
        "positive in test": int(yt.sum()),
        "PR-AUC": average_precision_score(yt, p) if yt.sum() else float("nan"),
        "ROC-AUC": roc_auc_score(yt, p) if 0 < yt.sum() < len(yt) else float("nan"),
        "precision@100": precision_at_k(yt, p, 100),
        "accuracy": float(((p > 0.5) == yt).mean()),
        "parameters": sum(q.numel() for q in model.parameters()),
    }


def main():
    b = torch.load(
        HERE.parent / "build" / "learning" / "food-graph.pt", weights_only=False
    )
    data = T.ToUndirected()(b["data"])  # messages flow both ways along every link
    y, category = b["y"].numpy(), b["category"].numpy()
    train, test = split_random(len(y), y)
    for s in range(3):
        r = run(data, y, train, test, seed=s)
        print(line(f"random split, training seed {s}", r))
    print(f"  ({r['parameters']:,} parameters)")
    for s in range(5):
        train, test = split_by_category(category, seed=s)
        print(line(f"split by category, seed {s}", run(data, y, train, test)))


if __name__ == "__main__":
    main()
