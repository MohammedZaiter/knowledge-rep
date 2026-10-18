"""Run the unmodified course learning algorithms with FoodScope inputs and save outputs."""

import json
import os
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "build/learning"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for filename in ("build_graph.py", "baseline.py", "gnn.py", "link_prediction.py"):
        print(f"Learning: {filename}", flush=True)
        env = dict(
            os.environ,
            OMP_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            PYTHONIOENCODING="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(HERE / filename)],
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        (OUT / filename.replace(".py", ".txt")).write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
        if result.returncode:
            raise SystemExit(
                f"{filename} failed; see {OUT / filename.replace('.py', '.txt')}\n{result.stderr[-1500:]}"
            )
        print(result.stdout, flush=True)
        # Group-split rows are the comparison; exclude guessing, leak and random-split demonstrations.
        grouped = [
            float(value)
            for value in re.findall(
                r"split by category[^\n]*PR-AUC (\d+\.\d+)", result.stdout
            )
        ]
        group_runs = []
        for line in result.stdout.splitlines():
            seed = re.search(r"split by category, seed (\d+)", line)
            if seed:
                score = re.search(r"PR-AUC (\d+\.\d+)", line)
                group_runs.append(
                    {
                        "seed": int(seed.group(1)),
                        "pr_auc": float(score.group(1)) if score else None,
                        "status": "scored" if score else "no positive test examples",
                    }
                )
        link_scores = {}
        for model in ("TransE", "popularity"):
            ranks = [
                float(value)
                for value in re.findall(model + r"\s+MRR (\d+\.\d+)", result.stdout)
            ]
            if ranks:
                link_scores[model] = {
                    "mrr": ranks,
                    "mean": statistics.fmean(ranks),
                    "sd": statistics.pstdev(ranks),
                }
        summaries[filename] = {
            "group_runs": group_runs,
            "link_prediction": link_scores,
            "group_pr_auc": grouped,
            "group_pr_auc_mean": statistics.fmean(grouped) if grouped else None,
            "group_pr_auc_sd": statistics.pstdev(grouped) if grouped else None,
            "log": filename.replace(".py", ".txt"),
        }
    (OUT / "evaluation.json").write_text(
        json.dumps(
            {
                "utc": datetime.now(timezone.utc).isoformat(),
                "classification": "fat > 20 g per 100 g; missing target excluded",
                "configuration": {
                    "gnn_epochs": 100,
                    "hidden": 32,
                    "training_seeds": 3,
                    "group_seeds": 5,
                    "transe_epochs": 150,
                    "transe_seeds": 3,
                },
                "group": "USDA category",
                "link_prediction": "category contains food; inverse category facts withheld",
                "results": summaries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
