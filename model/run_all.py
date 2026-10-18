"""Run our learning experiments in order and save each output in model/results/.

    python pipeline/run.py --no-load    first: writes build/graph.nt
    python model/run_all.py

Each script's printed output goes to model/results/<script>.txt, and
run-metadata.json records the date, the package versions and a hash of the
graph the run read. The report quotes only these files.
"""

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = HERE / "results"
GRAPH = ROOT / "build" / "graph.nt"
SCRIPTS = (
    "build_graph.py",
    "baseline.py",
    "gnn.py",
    "link_prediction.py",
    "tie_check.py",
)
PACKAGES = ("torch", "torch-geometric", "pykeen", "scikit-learn", "numpy", "rdflib")


def graph_hash():
    """Morph-KGC writes triples in any order: hash them sorted, so the same graph has one hash."""
    lines = sorted(GRAPH.read_text(encoding="utf-8").splitlines())
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def main():
    if not GRAPH.exists():
        sys.exit(
            "build/graph.nt not found: run python pipeline/run.py --no-load first."
        )
    RESULTS.mkdir(exist_ok=True)
    for script in SCRIPTS:
        out = RESULTS / (script.removesuffix(".py") + ".txt")
        print(f"{script} -> model/results/{out.name}", flush=True)
        run = subprocess.run(
            [sys.executable, str(HERE / script)],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        out.write_text(run.stdout, encoding="utf-8")
        if run.returncode:
            sys.exit(f"{script} failed:\n{run.stderr[-2000:]}")
    meta = {
        "utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "versions": {name: version(name) for name in PACKAGES},
        "source_graph": "build/graph.nt",
        "source_graph_sorted_sha256": graph_hash(),
        "platform": platform.platform(),
        "note": "All seeds reported; no best-seed selection.",
    }
    (RESULTS / "run-metadata.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print("done: model/results/run-metadata.json")


if __name__ == "__main__":
    main()
