# ruff: noqa: E402
"""The graph pipeline: source tables -> graph -> SHACL gate -> reasoner -> VoID -> endpoint.

    python pipeline/run.py              all steps, loads the endpoint at the end
    python pipeline/run.py --no-load    every step except the load (no Fuseki needed)

Run from the repository root. In the stack, docker compose runs it once, as
the "pipeline" service, before the access layer starts.

  1 source     DB_URL if set (your database), otherwise the example:
               data/example.sql loaded into build/example.sqlite
  2 map        mapping/mapping.ttl with Morph-KGC -> build/graph.nt,
               and one named graph per source table -> build/food.trig
  3 validate   build/graph.nt + ontology/ontology.ttl against shapes/shapes.ttl;
               any Violation stops here (exit 1), so bad data never reaches
               the endpoint; the report goes to build/shacl-report.txt
  4 reason     HermiT adds the inferred CharacterizedFood types;
               an inconsistency stops here -> build/reasoning.json
  5 query      sparql/queries.sparql on the reasoned graph -> build/answers.json
  6 describe   VoID of the graph -> build/void.ttl (the access layer reads it)
  7 load       reasoned graph and ontology into the endpoint (FUSEKI_URL, dataset kr)
  8 provenance PROV-O for the sources and this run -> build/provenance.ttl

Profiling, entity resolution and the graph models are not part of the path
to the endpoint; each runs on its own, see the README of data/, mapping/ and
model/.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from pyshacl import validate
from rdflib import RDF, Dataset, Graph, Namespace, URIRef
from validate import focus_counts

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
    step(6, f"describe: {n} VoID triples -> build/void.ttl")


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
    step(7, f"load: graph and ontology -> {base}")


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
        sys.exit("SHACL gate: a shape has no focus nodes; check its target class.")
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
        f"validate: {violations} Violation, {warnings} Warning -> build/shacl-report.txt",
    )
    if violations:
        sys.exit(
            "SHACL gate: the data has Violations, so the endpoint is not loaded. Read build/shacl-report.txt."
        )


def reason(graph):
    """HermiT through ontology/local_reasoner.py; inconsistency stops the pipeline."""
    before = len(graph)
    input_path = BUILD / "validation-input.ttl"
    world = hermit_reason(input_path)
    try:
        diagnostics = hermit_summary(world)
        result = {
            "engine": "HermiT via owlready2",
            "input_triples": before,
            **diagnostics,
        }
        if not diagnostics["inconsistent"] and not diagnostics["impossible"]:
            graph += world.as_rdflib_graph()
        result["closure_triples"] = len(graph)
        result["inferred_characterized_foods"] = len(
            set(graph.subjects(RDF.type, FOOD.CharacterizedFood))
        )
        # owlready2 lists no individuals for this data, so count the closure's types instead.
        result.pop("types", None)
        result["individuals_per_class"] = dict(
            sorted(
                Counter(
                    str(cls)
                    for node, cls in graph.subject_objects(RDF.type)
                    if "/kr/id/" in str(node) and isinstance(cls, URIRef)
                ).items()
            )
        )
        (BUILD / "reasoning.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        if diagnostics["inconsistent"] or diagnostics["impossible"]:
            sys.exit(
                "Reasoner: HermiT found an inconsistency or an impossible class. Read build/reasoning.json."
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
    (BUILD / "answers.json").write_text(json.dumps(answers, indent=2), encoding="utf-8")
    step(5, f"query: {len(answers)} questions answered -> build/answers.json")
    return answers


def write_named_graphs(graph):
    """One named graph per source table, for provenance."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-load", action="store_true")
    args = parser.parse_args()
    BUILD.mkdir(exist_ok=True)

    graph = materialize(source())
    step(2, f"map: {len(graph)} triples -> build/graph.nt")
    write_named_graphs(graph)

    # The gate sees the data with the ontology and its FoodOn import, as HermiT and Protege do.
    graph += merged_graph(ROOT / "ontology" / "ontology.ttl")
    graph.serialize(BUILD / "validation-input.ttl", format="turtle")
    validate_graph(graph)

    result = reason(graph)
    step(
        4,
        f"reason: {result['inferred_characterized_foods']} characterized foods -> build/reasoning.json",
    )
    execute_queries()
    describe(BUILD / "reasoned.ttl")
    if not args.no_load:
        load(BUILD / "reasoned.nt")

    from provenance import main as add_provenance

    add_provenance()
    step(8, "provenance: build/provenance.ttl")
    print("done")


if __name__ == "__main__":
    main()
