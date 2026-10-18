# ruff: noqa: E731
"""Course Session 5 run_ontop.py. Runs the same Ontop CLI over the FoodScope R2RML mapping and PostgreSQL source, prints CSV/SQL and records credential-redacted logs, results and wall time under build/ontop. Uses a UTF-8 query file without a byte-order mark."""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
CLI = HERE / "ontop-cli" / ("ontop.bat" if platform.system() == "Windows" else "ontop")


def main():
    from connection import database_url, java_environment, write_properties
    from sqlalchemy.engine import make_url

    java_environment()
    write_properties()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--query", default=str(HERE / "food-count.sparql"))
    args = ap.parse_args()
    if not CLI.exists():
        sys.exit(
            "Ontop is not installed yet: run python ontop/setup_ontop.py first. "
            "No Java or Docker? Read reference-outputs/ontop-q2.txt instead."
        )
    # Ontop's command line inconsistently treats these inputs as file paths
    # and URIs.  Relative paths avoid both interpretations of the spaces in
    # the course's macOS location ("Mobile Documents").
    relative = lambda path: os.path.relpath(Path(path).resolve(), LAB)
    with tempfile.NamedTemporaryFile(
        prefix="ontop-results-", suffix=".csv", delete=False
    ) as output:
        output_path = Path(output.name)
    cmd = [
        str(CLI),
        "query",
        "-m",
        "mapping/mapping.ttl",
        "-t",
        "build/ontop/ontology.ttl",
        "-p",
        "build/ontop/.food.properties",
        "-q",
        relative(args.query),
        "-o",
        str(output_path),
    ]
    env = dict(os.environ, ONTOP_LOG_LEVEL="DEBUG")
    try:
        started = time.perf_counter()
        run = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=LAB)
        log = run.stdout + "\n" + run.stderr
        password = make_url(database_url()).password
        if password:
            log = log.replace(password, "[redacted]")
        (LAB / "build/ontop/last-run.log").write_text(log, encoding="utf-8")
        if run.returncode != 0 or "Exception:" in log:
            if "Connection refused" in log or "Operation not permitted" in log:
                sys.exit(
                    "PostgreSQL is not answering on 127.0.0.1:5432: run `docker compose up -d` and "
                    "`python load_database.py`."
                )
            sys.exit(
                f"Ontop reported an error (CLI exit {run.returncode}); read build/ontop/last-run.log."
            )
        answers = output_path.read_text(encoding="utf-8").splitlines()
        (LAB / "build/ontop/last-results.csv").write_text(
            "\n".join(answers) + "\n", encoding="utf-8"
        )
        (LAB / "build/ontop/timing.json").write_text(
            json.dumps(
                {
                    "seconds": time.perf_counter() - started,
                    "query": Path(args.query).read_text(),
                },
                indent=2,
            )
        )
    finally:
        output_path.unlink(missing_ok=True)
    print("Answers (CSV):")
    for line in answers:
        print("  " + line)
    sql = re.findall(r"(?is)(SELECT\s.+?)(?:\n\s*\n|\n\d\d:\d\d:\d\d)", log)
    sql = [s for s in sql if "FROM" in s.upper() and "foods" in s.lower()]
    print(
        "\nThe SQL Ontop sent to PostgreSQL:"
        if sql
        else "\nNo SQL found in the log; see ontop/last-run.log."
    )
    if sql:
        print(max(sql, key=len).strip())


if __name__ == "__main__":
    main()
