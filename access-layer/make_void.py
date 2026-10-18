"""Describe the graph with VoID: which classes it has, how many of each, and
which properties link each class to which class or datatype (the layout of
SIB's void-generator). The access layer tells the model this, not the whole
ontology, and checks every query against it.

    python access-layer/make_void.py build/graph.nt build/void.ttl

pipeline/run.py calls write_void() after the SHACL gate.
"""

import sys
from pathlib import Path

import pyoxigraph as ox
from access_layer import DATASET, NS, PFX

QUERY = f"""
PREFIX void: <http://rdfs.org/ns/void#>
PREFIX void-ext: <http://ldf.fi/void-ext#>
CONSTRUCT {{
  <{DATASET}> void:classPartition ?cp .
  ?cp void:class ?c ; void:entities ?n ; void:propertyPartition ?pp .
  ?pp void:property ?p ; void:triples ?t ; void:classPartition ?op ; void-ext:datatypePartition ?dp .
  ?op void:class ?oc .
  ?dp void-ext:datatype ?dt .
}} WHERE {{
  {{ SELECT ?c (COUNT(DISTINCT ?s) AS ?n) WHERE {{ ?s a ?c FILTER STRSTARTS(STR(?c), "{NS}") }} GROUP BY ?c }}
  BIND (IRI(CONCAT(STR(?c), "-partition")) AS ?cp)
  OPTIONAL {{
    {{ SELECT ?c ?p (COUNT(*) AS ?t) (SAMPLE(?ocls) AS ?oc) (SAMPLE(DATATYPE(?o)) AS ?dt0) WHERE {{
        ?s a ?c ; ?p ?o . FILTER (?p != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
        OPTIONAL {{ ?o a ?ocls }} }} GROUP BY ?c ?p }}
    BIND (IRI(CONCAT(STR(?c), "-", STRAFTER(STR(?p), "#"))) AS ?pp)
    BIND (IF(BOUND(?oc), IRI(CONCAT(STR(?pp), "-class")), ?unbound) AS ?op)
    BIND (IF(BOUND(?dt0) && !BOUND(?oc), ?dt0, ?unbound) AS ?dt)
    BIND (IF(BOUND(?dt), IRI(CONCAT(STR(?pp), "-datatype")), ?unbound) AS ?dp)
  }}
}}
"""


def write_void(graph_path, out_path):
    store = ox.Store()
    fmt = (
        ox.RdfFormat.N_TRIPLES
        if str(graph_path).endswith(".nt")
        else ox.RdfFormat.TURTLE
    )
    store.bulk_load(path=str(graph_path), format=fmt)
    triples = list(store.query(QUERY))
    Path(out_path).write_bytes(
        ox.serialize(
            triples,
            format=ox.RdfFormat.TURTLE,
            prefixes={
                "void": "http://rdfs.org/ns/void#",
                "void-ext": "http://ldf.fi/void-ext#",
                PFX: NS,
            },
        )
    )
    return len(triples)


if __name__ == "__main__":
    print(write_void(sys.argv[1], sys.argv[2]), "VoID triples")
