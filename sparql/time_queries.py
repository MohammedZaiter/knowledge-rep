"""Time each query of queries.sparql on the reasoned graph, in Oxigraph.

    python pipeline/run.py --no-load
    python sparql/time_queries.py > sparql/query-timings.txt

Each query runs five times; the median is reported, without the time to load
the graph. A query against Fuseki (the Docker stack) adds the HTTP round trip.
"""

import re
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import pyoxigraph as ox

ROOT = Path(__file__).resolve().parents[1]
RUNS = 5


def main():
    store = ox.Store()
    t0 = time.perf_counter()
    store.load(path=str(ROOT / "build" / "reasoned.ttl"), format=ox.RdfFormat.TURTLE)
    loaded = time.perf_counter() - t0
    text = (ROOT / "sparql" / "queries.sparql").read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^# QUERY: (.+)\n", text)
    print(f"Oxigraph {ox.__version__}, {len(store):,} triples loaded in {loaded:.2f} s")
    print(f"UTC {datetime.now(UTC).replace(microsecond=0).isoformat()}")
    print(f"median of {RUNS} runs per query\n")
    for i in range(1, len(blocks), 2):
        title, query = blocks[i], blocks[i + 1].strip()
        times, rows = [], 0
        for _ in range(RUNS):
            t = time.perf_counter()
            rows = sum(1 for _ in store.query(query))
            times.append(time.perf_counter() - t)
        ms = statistics.median(times) * 1000
        print(f"Q{(i + 1) // 2:<3} {ms:7.2f} ms  {rows:>4} rows  {title}")


if __name__ == "__main__":
    main()
