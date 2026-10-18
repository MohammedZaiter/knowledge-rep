"""Compare the course materialized graph and Ontop over the same four source tables."""

import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pyoxigraph as ox

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    query = ROOT / "mapping/ontop/food-count.sparql"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "mapping/ontop/run_ontop.py"),
            "--query",
            str(query),
        ],
        check=True,
    )
    store = ox.Store()
    store.bulk_load(path=str(ROOT / "build/graph.nt"), format=ox.RdfFormat.N_TRIPLES)
    started = time.perf_counter()
    result = store.query(query.read_text(encoding="utf-8-sig"))
    rows = [[str(value.value) for value in row] for row in result]
    seconds = time.perf_counter() - started
    with (ROOT / "build/ontop/last-results.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        virtual = list(csv.reader(stream))[1:]
    warnings = [
        line
        for line in (ROOT / "build/ontop/last-run.log")
        .read_text(encoding="utf-8")
        .splitlines()
        if "Axiom does not belong to OWL 2 QL" in line
    ]
    report = {
        "ontop_profile_warnings": warnings,
        "utc": datetime.now(timezone.utc).isoformat(),
        "query": query.read_text(encoding="utf-8-sig"),
        "materialized_rows": rows,
        "virtualized_rows": virtual,
        "same_answers": sorted(rows) == sorted(virtual),
        "materialized_query_seconds": seconds,
        "virtualized_timing": json.loads(
            (ROOT / "build/ontop/timing.json").read_text()
        ),
        "timing_scope": "Ontop includes JVM startup; Oxigraph timing excludes graph loading; not an engine-only latency benchmark.",
    }
    (ROOT / "mapping/virtualization-comparison.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    if not report["same_answers"]:
        raise SystemExit("Materialized and virtualized answers differ.")
    print(
        "Materialized and Ontop answers match; see mapping/virtualization-comparison.json"
    )
