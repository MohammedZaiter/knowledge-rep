# ruff: noqa: E402
"""Run the local KRR pipeline: profile, load SQLite, map RDF, validate, reason, query."""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from pyshacl import validate
from rdflib import RDF, Dataset, Graph, Namespace, URIRef
from validation.validate import focus_counts

from data.profiling.data_profile import profile
from ontology.local_reasoner import merged_graph
from ontology.local_reasoner import reason as hermit_reason
from ontology.local_reasoner import summary as hermit_summary

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
BUILD = ROOT / "build"
FOOD = Namespace("https://ul.edu.lb/kr/food#")
SH = Namespace("http://www.w3.org/ns/shacl#")
FUSEKI = os.environ.get("FUSEKI_URL", "http://127.0.0.1:3030")
DATASET = os.environ.get("FUSEKI_DATASET", "kr")



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

    cfg = (
        f"[CONFIGURATION]\nlogging_level=WARNING\nnumber_of_processes=1\n\n"
        f"[source]\nmappings={ROOT / 'mapping' / 'mapping.ttl'}\ndb_url={database}\n"
    )
    graph = morph_kgc.materialize(cfg)
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


def execute_queries():
    """Execute named SELECT/ASK queries from queries.sparql on the inferred graph."""
    import pyoxigraph as ox

    store = ox.Store()
    store.load(path=str(BUILD / "reasoned.ttl"), format=ox.RdfFormat.TURTLE)
    text = (ROOT / "sparql" / "queries.sparql").read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^# QUERY: (.+)\n", text)
    if len(blocks) < 3:
        raise ValueError("No queries found. Use '# QUERY: title' before each query.")
    answers = []
    for index in range(1, len(blocks), 2):
        title, query = blocks[index], blocks[index + 1].strip()
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
        answers.append({"question": title, "query": query, "rows": rows})
        print(f"  {title}: {len(rows) if isinstance(rows, list) else rows}")
    (BUILD / "answers.json").write_text(json.dumps(answers, indent=2), encoding="utf-8")
    return answers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-load", action="store_true")

    args = parser.parse_args()
    BUILD.mkdir(exist_ok=True)
    subprocess.run(
        [sys.executable, str(ROOT / "data/profiling/source_profile.py")], check=True
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

    execute_queries()
    subprocess.run(
        [sys.executable, str(ROOT / "mapping/er/match_foods.py")], check=True
    )

    for script in ("build_graph.py", "baseline.py", "gnn.py", "link_prediction.py"):
        subprocess.run([sys.executable, str(ROOT / "model" / script)], check=True)

    describe(BUILD / "reasoned.ttl")

    if not args.no_load:
        load(BUILD / "reasoned.nt")
    from provenance.add_provenance import main as add_provenance

    add_provenance()
    print("Done. Results are in build/.")


if __name__ == "__main__":
    main()
