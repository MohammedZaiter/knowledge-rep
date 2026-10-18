"""Course Session 2 load_fuseki.py adapted to build/reasoned.ttl and FUSEKI_BASE. Same default-graph HTTP PUT and endpoint confirmation."""

import os
import time
from pathlib import Path

import requests

FUSEKI_BASE = os.environ.get("FUSEKI_BASE", "http://127.0.0.1:3030")
DATASET = "kr"
TTL_PATH = Path(__file__).resolve().parents[1] / "build" / "reasoned.ttl"


def load():
    start = time.perf_counter()
    resp = requests.put(
        f"{FUSEKI_BASE}/{DATASET}/data?default",
        data=TTL_PATH.read_bytes(),
        headers={"Content-Type": "text/turtle"},
        timeout=600,
    )
    resp.raise_for_status()
    print(
        f"Loaded {TTL_PATH.name} into {FUSEKI_BASE}/{DATASET} in {time.perf_counter() - start:.1f} s"
    )


def confirm():
    resp = requests.get(
        f"{FUSEKI_BASE}/{DATASET}/sparql",
        params={"query": "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=60,
    )
    resp.raise_for_status()
    n = resp.json()["results"]["bindings"][0]["n"]["value"]
    print(f"Endpoint answers: {n} triples loaded.")


if __name__ == "__main__":
    try:
        load()
        confirm()
    except requests.ConnectionError:
        raise SystemExit(
            "Fuseki is not answering on http://localhost:3030. Start it from demos/ "
            "with `docker compose up -d`, or skip this step and use Oxigraph: "
            "python run_queries.py oxigraph"
        )
