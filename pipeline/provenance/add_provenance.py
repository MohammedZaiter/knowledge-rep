"""Course Session 4 add_provenance.py adapted to USDA tables. Records PROV-O entities, activities, software, hashes, times and named-source graphs; answers the provenance of one food-name fact."""

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from rdflib import RDF, RDFS, XSD, Dataset, Graph, Literal, Namespace, URIRef

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = "https://ul.edu.lb/kr/id/"
SOURCE_TABLES = {
    name: ROOT / "data" / f"{name}.csv"
    for name in ("foods", "measurements", "nutrients", "categories")
}


def graph_iri(source, table):
    return f"{DATA}graph/{source}/{table}"


TRIG = ROOT / "build" / "food.trig"
CONVERTER = ROOT / "pipeline/run.py"
PROV = Namespace("http://www.w3.org/ns/prov#")
DCT = Namespace("http://purl.org/dc/terms/")
VOID = Namespace("http://rdfs.org/ns/void#")
TABLE_FILE = {name: name for name in SOURCE_TABLES}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def when(path):
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(
        microsecond=0
    )


def main():
    if not TRIG.exists():
        sys.exit(
            "brunel.trig not found: run python convert_to_rdf.py in demos/session-02-rdf-sparql/ first."
        )
    ds = Dataset()
    ds.parse(TRIG, format="trig")
    made = when(TRIG)

    g = Graph()
    for p, ns in (
        ("prov", PROV),
        ("dcterms", DCT),
        ("void", VOID),
        ("xsd", XSD),
        ("rdfs", RDFS),
    ):
        g.bind(p, ns)
    run = URIRef(f"{DATA}run/usda/convert-{made.strftime('%Y%m%dT%H%M%SZ')}")
    program = URIRef(f"{DATA}software/foodscope/run.py")
    g.add((program, RDF.type, PROV.SoftwareAgent))
    g.add((program, RDFS.label, Literal("run.py (course R2RML adaptation)")))
    g.add((program, DCT.identifier, Literal("sha256:" + sha256(CONVERTER))))
    g.add((run, RDF.type, PROV.Activity))
    g.add((run, RDFS.label, Literal("FoodScope USDA mapping run")))
    g.add((run, PROV.wasAssociatedWith, program))
    g.add((run, PROV.endedAtTime, Literal(made.isoformat(), datatype=XSD.dateTime)))

    rows = []
    for table, key in TABLE_FILE.items():
        csv = SOURCE_TABLES[key]
        f = URIRef(f"{DATA}file/brunel/{csv.name}")
        graph = URIRef(graph_iri("usda", table))
        n = len(ds.graph(graph))
        g.add((f, RDF.type, PROV.Entity))
        g.add((f, DCT.title, Literal(csv.name)))
        g.add((f, DCT.identifier, Literal("sha256:" + sha256(csv))))
        g.add((run, PROV.used, f))
        g.add((graph, RDF.type, PROV.Entity))
        g.add((graph, PROV.wasDerivedFrom, f))
        g.add((graph, PROV.wasGeneratedBy, run))
        g.add(
            (
                graph,
                PROV.generatedAtTime,
                Literal(made.isoformat(), datatype=XSD.dateTime),
            )
        )
        g.add((graph, VOID.triples, Literal(n)))
        rows.append((table, csv.name, n))
    out = ROOT / "build" / "provenance.ttl"
    g.serialize(out, format="turtle")
    print(
        f"provenance.ttl: {len(g)} triples about {len(rows)} named graphs, 1 run, 1 program"
    )
    for table, name, n in rows:
        print(f"  graph {table:<17} {n:>7,} triples  derived from {name}")

    # The question provenance answers: where did this one fact come from?
    ds.graph(URIRef(f"{DATA}graph/usda/provenance")).parse(out)
    q = """
    PREFIX ul: <https://ul.edu.lb/kr/food#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    SELECT ?g ?file ?run ?time WHERE {
      GRAPH ?g { <https://ul.edu.lb/kr/id/food/usda/323793> ul:name ?c }
      GRAPH ?p { ?g prov:wasDerivedFrom ?f ; prov:wasGeneratedBy ?run .
                 ?f dcterms:title ?file . ?run prov:endedAtTime ?time } }"""
    for r in ds.query(q):
        print("\nWhere does 'food 323793 name' come from?")
        print(
            f"  named graph {r.g}\n  file        {r.file}\n  run         {r.run}\n  finished    {r.time}"
        )


if __name__ == "__main__":
    main()
