"""Run the local KRR pipeline: profile, load SQLite, map RDF, validate, reason, query."""

import argparse
import configparser
import hashlib
import io
import json
import re
import sqlite3
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from data.prepare import read_csv
from owlrl import DeductiveClosure, OWLRL_Semantics
from profiling.data_profile import profile
from pyshacl import validate
from rdflib import OWL, RDF, Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
BUILD = ROOT / "build"
FOOD = Namespace("https://ul.edu.lb/kr/food#")
SH = Namespace("http://www.w3.org/ns/shacl#")
TABLES = {
    "foods": "foods.csv",
    "measurements": "measurements.csv",
    "nutrients": "nutrients.csv",
    "categories": "categories.csv",
}


def load_database():
    """Rebuild local tables from CSV; no server or network connection is needed."""
    database = BUILD / "food.sqlite"
    with sqlite3.connect(database) as connection:
        for table, filename in TABLES.items():
            rows = read_csv(DATA / filename)
            if not rows:
                raise ValueError(f"Input table is empty: {filename}")
            columns = list(rows[0])
            definitions = ", ".join(f'"{column}" TEXT' for column in columns)
            connection.execute(f'DROP TABLE IF EXISTS "{table}"')
            connection.execute(f'CREATE TABLE "{table}" ({definitions})')
            placeholders = ", ".join("?" for _ in columns)
            values = [
                tuple(row[column] if row[column] != "" else None for column in columns)
                for row in rows
            ]
            connection.executemany(
                f'INSERT INTO "{table}" VALUES ({placeholders})', values
            )
    return database


def materialize(database):
    """Execute the R2RML mapping with the same Morph-KGC tool used in the course."""
    import morph_kgc

    configuration = configparser.ConfigParser(interpolation=None)
    configuration.read_dict(
        {
            "CONFIGURATION": {"logging_level": "WARNING", "number_of_processes": "1"},
            "source": {
                "mappings": str(ROOT / "mapping" / "mapping.ttl"),
                "db_url": f"sqlite:///{database.as_posix()}",
            },
        }
    )
    buffer = io.StringIO()
    configuration.write(buffer)
    graph = morph_kgc.materialize(buffer.getvalue())
    expected_foods = len(read_csv(DATA / "foods.csv"))
    actual_foods = len(set(graph.subjects(RDF.type, FOOD.Food)))
    if actual_foods != expected_foods:
        raise ValueError(
            f"Mapping lost food rows: {actual_foods} nodes for {expected_foods} rows"
        )
    graph.serialize(BUILD / "graph.nt", format="nt", encoding="utf-8")
    return graph


def validate_graph(graph):
    """Reject violations and empty shape targets; preserve completeness warnings."""
    shapes = Graph().parse(ROOT / "shapes" / "shapes.ttl")
    coverage = {
        str(shape): len(set(graph.subjects(RDF.type, target)))
        for shape, target in shapes.subject_objects(SH.targetClass)
    }
    (BUILD / "shape_coverage.json").write_text(
        json.dumps(coverage, indent=2), encoding="utf-8"
    )
    if not coverage or any(count == 0 for count in coverage.values()):
        raise ValueError("A SHACL shape has no focus nodes; check its target class.")
    _, report, description = validate(
        graph, shacl_graph=shapes, inference="none", allow_warnings=True
    )
    report.serialize(BUILD / "validation.ttl", format="turtle")
    (BUILD / "validation.txt").write_text(description, encoding="utf-8")
    violations = len(list(report.subjects(SH.resultSeverity, SH.Violation)))
    warnings = len(list(report.subjects(SH.resultSeverity, SH.Warning)))
    print(f"Validation: {violations} violations, {warnings} warnings.")
    if violations:
        raise ValueError(
            "SHACL gate failed. Read build/validation.txt; queries were not executed."
        )


def reason(graph):
    """Compute OWL RL closure and check for reported contradictions."""
    before = len(graph)
    DeductiveClosure(OWLRL_Semantics).expand(graph)
    clashes = {str(node) for node in graph.subjects(RDF.type, OWL.Nothing)}
    for first, second in graph.subject_objects(OWL.disjointWith):
        clashes.update(
            str(node)
            for node in set(graph.subjects(RDF.type, first))
            & set(graph.subjects(RDF.type, second))
        )
    error_property = URIRef("http://www.daml.org/2002/03/agents/agent-ont#error")
    errors = [str(value) for value in graph.objects(None, error_property)]
    result = {
        "engine": "OWL RL rule closure (not a complete OWL DL reasoner)",
        "scope": "Local food ontology, asserted FoodOn ancestor extract, and USDA facts",
        "input_triples": before,
        "closure_triples": len(graph),
        "inferred_characterized_foods": len(
            set(graph.subjects(RDF.type, FOOD.CharacterizedFood))
        ),
        "clashes": sorted(clashes),
        "rule_errors": errors,
    }
    (BUILD / "reasoning.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    if clashes or errors:
        raise ValueError("OWL RL reported a contradiction. Read build/reasoning.json.")
    graph.serialize(BUILD / "reasoned.ttl", format="turtle")
    return result


def execute_queries(graph):
    """Execute named SELECT/ASK queries from queries.sparql on the inferred graph."""
    text = (ROOT / "sparql" / "queries.sparql").read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^# QUERY: (.+)\n", text)
    if len(blocks) < 3:
        raise ValueError("No queries found. Use '# QUERY: title' before each query.")
    answers = []
    for index in range(1, len(blocks), 2):
        title, query = blocks[index], blocks[index + 1].strip()
        result = graph.query(query)
        if result.type == "ASK":
            rows = bool(result.askAnswer)
        elif result.type == "SELECT":
            rows = [
                {str(key): str(value) for key, value in row.asdict().items()}
                for row in result
            ]
        else:
            raise ValueError("This runner supports SELECT and ASK queries only.")
        answers.append({"question": title, "query": query, "rows": rows})
        print(f"  {title}: {len(rows) if isinstance(rows, list) else rows}")
    (BUILD / "answers.json").write_text(json.dumps(answers, indent=2), encoding="utf-8")
    return answers


def record_provenance():
    """Record the input hashes and run time next to the generated outputs."""
    files = [DATA / filename for filename in TABLES.values()]
    files += [
        ROOT / name
        for name in (
            "data/prepare.py",
            "profiling/data_profile.py",
            "run.py",
            "mapping/mapping.ttl",
            "ontology/ontology.ttl",
            "shapes/shapes.ttl",
            "sparql/queries.sparql",
        )
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
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT.parent))
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
        help="Build, validate and reason without executing SPARQL",
    )
    parser.add_argument(
        "--no-ui", action="store_true", help="Run the pipeline without starting the UI"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Local UI port (default: 8000)"
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    BUILD.mkdir(exist_ok=True)
    report = profile()
    print(f"Profile: {report['foods']} foods, {report['observations']} observations.")
    database = load_database()
    print(f"Loaded SQLite: {database.name}")
    graph = materialize(database)
    print(f"Mapped RDF: {len(graph)} triples.")
    graph.parse(ROOT / "ontology" / "ontology.ttl")
    validate_graph(graph)
    result = reason(graph)
    print(f"Reasoning: {result['inferred_characterized_foods']} characterized foods.")
    if not args.skip_queries:
        execute_queries(graph)
    record_provenance()
    print("Done. Results are in build/.")
    if not args.no_ui and not args.skip_queries:
        serve_ui(args.port)


if __name__ == "__main__":
    main()
