# ruff: noqa: E402
"""Run the local KRR pipeline: profile, load SQLite, map RDF, validate, reason, query."""

import argparse
import configparser
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from pyshacl import validate
from rdflib import RDF, Dataset, Graph, Namespace, URIRef
from validation.validate import focus_counts

from data.prepare import read_csv
from data.profiling.data_profile import profile
from ontology.local_reasoner import merged_graph
from ontology.local_reasoner import reason as hermit_reason
from ontology.local_reasoner import summary as hermit_summary

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
if not os.environ.get("JAVA_EXE") and not shutil.which("java"):
    portable_java = next((ROOT / ".tools" / "java").glob("*/bin/java.exe"), None)
    if portable_java:
        os.environ["JAVA_EXE"] = str(portable_java)
DATA = ROOT / "data"
BUILD = ROOT / "build"
FOOD = Namespace("https://ul.edu.lb/kr/food#")
SH = Namespace("http://www.w3.org/ns/shacl#")
FUSEKI = os.environ.get("FUSEKI_URL", "http://127.0.0.1:3030")
DATASET = os.environ.get("FUSEKI_DATASET", "kr")
TABLES = {
    "foods": "foods.csv",
    "measurements": "measurements.csv",
    "nutrients": "nutrients.csv",
    "categories": "categories.csv",
}


def step(n, text):
    print(f"{n} {text}", flush=True)


def source():
    url = os.environ.get("DB_URL")
    if url:
        step(1, f"source: {url.split('@')[-1]}")  # never print a password
        return url
    db = BUILD / "example.sqlite"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript((ROOT / "data" / "example.sql").read_text(encoding="utf-8"))
    con.close()
    step(1, "source: the example, data/example.sql")
    return f"sqlite:///{db}"


def describe(graph_path):
    sys.path.insert(0, str(ROOT / "access-layer"))
    from make_void import write_void

    n = write_void(graph_path, BUILD / "void.ttl")
    step(4, f"describe: {n} VoID triples -> build/void.ttl")


def load(graph_path):
    base = f"{FUSEKI}/{DATASET}"
    for _ in range(30):  # the endpoint may still be starting
        try:
            if requests.get(f"{FUSEKI}/$/ping", timeout=5).ok:
                break
        except requests.ConnectionError:
            pass
        time.sleep(2)
    else:
        sys.exit(f"The endpoint at {FUSEKI} did not answer within a minute.")
    ont = (ROOT / "ontology" / "ontology.ttl").read_bytes()
    r1 = requests.put(
        f"{base}/data?default",
        data=graph_path.read_bytes(),
        headers={"Content-Type": "application/n-triples"},
        timeout=300,
    )
    r2 = requests.post(
        f"{base}/data?default",
        data=ont,
        headers={"Content-Type": "text/turtle"},
        timeout=60,
    )
    for r in (r1, r2):
        if not r.ok:
            sys.exit(f"Loading the endpoint failed ({r.status_code}): {r.text[:200]}")
    step(5, f"load: graph and ontology -> {base}")


def materialize(database):
    """Execute the R2RML mapping with the same Morph-KGC tool used in the course."""
    import morph_kgc

    configuration = configparser.ConfigParser(interpolation=None)
    configuration.read_dict(
        {
            "CONFIGURATION": {"logging_level": "WARNING", "number_of_processes": "1"},
            "source": {
                "mappings": str(ROOT / "mapping" / "mapping.ttl"),
                "db_url": database,
            },
        }
    )
    buffer = io.StringIO()
    configuration.write(buffer)
    graph = morph_kgc.materialize(buffer.getvalue())
    expected_foods = (
        len(read_csv(DATA / "foods.csv")) if not os.environ.get("DB_URL") else None
    )
    actual_foods = len(set(graph.subjects(RDF.type, FOOD.Food)))
    if expected_foods is not None and actual_foods != expected_foods:
        raise ValueError(
            f"Mapping lost food rows: {actual_foods} nodes for {expected_foods} rows"
        )
    graph.serialize(BUILD / "graph.nt", format="nt", encoding="utf-8")
    return graph


def validate_graph(graph):
    """Reject violations and empty shape targets; preserve completeness warnings."""
    shapes = Graph().parse(ROOT / "shapes" / "shapes.ttl")
    coverage = {
        str(shape): count for shape, count in focus_counts(graph, shapes).items()
    }
    (BUILD / "shape_coverage.json").write_text(
        json.dumps(coverage, indent=2), encoding="utf-8"
    )
    if not coverage or any(count == 0 for count in coverage.values()):
        raise ValueError("A SHACL shape has no focus nodes; check its target class.")
    _, report, description = validate(
        graph, shacl_graph=shapes, inference="none", advanced=True
    )
    report.serialize(BUILD / "validation.ttl", format="turtle")
    (BUILD / "validation.txt").write_text(description, encoding="utf-8")
    (BUILD / "shacl-report.txt").write_text(description, encoding="utf-8")
    violations = len(list(report.subjects(SH.resultSeverity, SH.Violation)))
    warnings = len(list(report.subjects(SH.resultSeverity, SH.Warning)))
    step(
        3,
        f"validate: {violations} violations, {warnings} warnings -> build/shacl-report.txt",
    )
    if violations:
        raise ValueError(
            "SHACL gate failed. Read build/validation.txt; queries were not executed."
        )


def reason(graph):
    """Course Session 3: HermiT through the copied local_reasoner.py."""
    before = len(graph)
    input_path = BUILD / "validation-input.ttl"
    world = hermit_reason(input_path)
    try:
        diagnostics = hermit_summary(world)
        result = {
            "engine": "HermiT via owlready2 (course Session 3)",
            "input_triples": before,
            **diagnostics,
        }
        if not diagnostics["inconsistent"] and not diagnostics["impossible"]:
            graph += world.as_rdflib_graph()
        result["closure_triples"] = len(graph)
        result["inferred_characterized_foods"] = len(
            set(graph.subjects(RDF.type, FOOD.CharacterizedFood))
        )
        (BUILD / "reasoning.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        if diagnostics["inconsistent"] or diagnostics["impossible"]:
            raise ValueError(
                "HermiT found an inconsistency or impossible local class. Read build/reasoning.json."
            )
        graph.serialize(BUILD / "reasoned.ttl", format="turtle")
        graph.serialize(BUILD / "reasoned.nt", format="nt", encoding="utf-8")
        return result
    finally:
        world.close()


def execute_queries(graph):
    """Execute named SELECT/ASK queries from queries.sparql on the inferred graph."""
    import pyoxigraph as ox

    store = ox.Store()
    store.load(path=str(BUILD / "reasoned.ttl"), format=ox.RdfFormat.TURTLE)
    timings = []
    text = (ROOT / "sparql" / "queries.sparql").read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^# QUERY: (.+)\n", text)
    if len(blocks) < 3:
        raise ValueError("No queries found. Use '# QUERY: title' before each query.")
    answers = []
    for index in range(1, len(blocks), 2):
        title, query = blocks[index], blocks[index + 1].strip()
        started = time.perf_counter()
        result = store.query(query)
        if isinstance(result, ox.QueryBoolean):
            rows = bool(result)
        elif isinstance(result, ox.QuerySolutions):
            columns = [variable.value for variable in result.variables]
            rows = [
                {
                    column: row[column].value
                    for column in columns
                    if row[column] is not None
                }
                for row in result
            ]
        else:
            raise ValueError("This runner supports SELECT and ASK queries only.")
        milliseconds = (time.perf_counter() - started) * 1000
        timings.append(
            {
                "question": title,
                "milliseconds": milliseconds,
                "rows": len(rows) if isinstance(rows, list) else rows,
            }
        )
        answers.append({"question": title, "query": query, "rows": rows})
        print(f"  {title}: {len(rows) if isinstance(rows, list) else rows}")
    (BUILD / "answers.json").write_text(json.dumps(answers, indent=2), encoding="utf-8")
    (BUILD / "query-timings.json").write_text(
        json.dumps(timings, indent=2), encoding="utf-8"
    )
    return answers


def record_provenance():
    """Record the input hashes and run time next to the generated outputs."""
    files = [DATA / filename for filename in TABLES.values()]
    files += [
        ROOT / name
        for name in (
            "data/prepare.py",
            "data/profiling/data_profile.py",
            "pipeline/run.py",
            "mapping/mapping.ttl",
            "ontology/ontology.ttl",
            "shapes/shapes.ttl",
            "sparql/queries.sparql",
        )
    ]
    files += [
        path
        for folder in (
            "ontology",
            "access-layer",
            "model",
            "pipeline/validation",
            "pipeline/provenance",
        )
        for path in (ROOT / folder).glob("*")
        if path.is_file() and path.suffix in (".py", ".ttl", ".yaml", ".xml")
    ]
    files += [
        ROOT / "pipeline/requirements-pipeline.txt",
        ROOT / "model/requirements.txt",
        DATA / "example.sql",
        DATA / "manifest.json",
        DATA / "foodon-source.json",
        DATA / "FOODON-LICENSE.txt",
    ]
    record = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
    }
    (BUILD / "provenance.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )


def serve_ui(port):
    """Serve the repository UI on loopback until the user presses Ctrl+C."""
    sys.path.insert(0, str(ROOT / "access-layer"))
    from serve import Handler

    handler = partial(Handler, directory=str(ROOT))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as error:
        raise SystemExit(
            f"Cannot start UI on port {port}: {error}. Try --port {port + 1}."
        ) from error
    with server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"UI: {url} (press Ctrl+C to stop)", flush=True)
        try:
            if not webbrowser.open(url):
                print(f"Open {url} in your browser.", flush=True)
        except webbrowser.Error:
            print(f"Open {url} in your browser.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nUI server stopped.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-queries",
        action="store_true",
        help="Skip predefined query answers; the template VoID description is still rebuilt",
    )
    parser.add_argument(
        "--no-ui", action="store_true", help="Run the pipeline without starting the UI"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Local UI port (default: 8000)"
    )
    parser.add_argument(
        "--skip-learning",
        action="store_true",
        help="Skip the course learning experiments",
    )
    parser.add_argument(
        "--skip-profile",
        action="store_true",
        help="Skip HTML profiling; constraint inventory is still generated",
    )
    parser.add_argument(
        "--no-load", action="store_true", help="Template local mode: do not load Fuseki"
    )
    parser.add_argument(
        "--ui", action="store_true", help="Start the local UI after the pipeline"
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    BUILD.mkdir(exist_ok=True)
    if not args.skip_profile:
        subprocess.run(
            [sys.executable, str(ROOT / "data" / "profiling" / "source_profile.py")],
            check=True,
        )
    report = profile()
    print(f"Profile: {report['foods']} foods, {report['observations']} observations.")
    database = source()
    graph = materialize(database)
    step(2, f"map: {len(graph)} triples -> build/graph.nt")
    # Same course offline-import resolution as HermiT/Protege.
    dataset = Dataset()
    for subject, predicate, obj in graph:
        table = (
            "measurements"
            if predicate == FOOD.hasObservation
            else {
                "food": "foods",
                "observation": "measurements",
                "nutrient": "nutrients",
                "category": "categories",
            }.get(str(subject).split("/id/")[-1].split("/")[0])
        )
        if table:
            dataset.graph(URIRef(f"https://ul.edu.lb/kr/id/graph/usda/{table}")).add(
                (subject, predicate, obj)
            )
    dataset.serialize(BUILD / "food.trig", format="trig")
    graph += merged_graph(ROOT / "ontology" / "ontology.ttl")
    graph.serialize(BUILD / "validation-input.ttl", format="turtle")
    validate_graph(graph)
    result = reason(graph)
    print(f"Reasoning: {result['inferred_characterized_foods']} characterized foods.")
    if not args.skip_queries:
        execute_queries(graph)
    subprocess.run(
        [sys.executable, str(ROOT / "mapping/er/match_foods.py")], check=True
    )
    if not args.skip_learning:
        subprocess.run(
            [sys.executable, str(ROOT / "model" / "run_learning.py")], check=True
        )
    describe(BUILD / "reasoned.ttl")
    if not args.no_load:
        load(BUILD / "reasoned.nt")
    from provenance.add_provenance import main as add_provenance

    add_provenance()
    record_provenance()
    print("Done. Results are in build/.")
    if args.ui and not args.no_ui and not args.skip_queries:
        serve_ui(args.port)


if __name__ == "__main__":
    main()
