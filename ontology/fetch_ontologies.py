"""Course Session 3 fetch_ontologies.py pattern, adapted to the recorded FoodOn release.

The course copies only the source subtrees it needs. FoodScope keeps only the
recorded three named classes, annotations and their named subclass edges.
Run with --source FILE to verify/extract an already downloaded original.
"""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DCT = Namespace("http://purl.org/dc/terms/")
MODULE = URIRef("https://ul.edu.lb/kr/food/foodon-module")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, help="Existing original FoodOn OWL source"
    )
    args = parser.parse_args()
    record = json.loads((ROOT / "data/foodon-source.json").read_text())
    source = args.source or ROOT / "data/raw/foodon/foodon.owl"
    if args.source is None and not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        url = record["ontology_versions"][0].replace("http://", "https://", 1)
        print(f"Downloading recorded release: {url}", flush=True)
        try:
            urllib.request.urlretrieve(url, source)
        except OSError:
            # Same source bytes are acceptable only if the recorded hash matches.
            print(
                "Recorded version URL unavailable; trying the recorded source URL with mandatory hash verification.",
                flush=True,
            )
            urllib.request.urlretrieve(record["source"], source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != record["sha256"]:
        raise SystemExit(
            "FoodOn source SHA-256 differs from data/foodon-source.json; refusing to replace the module."
        )
    original = Graph().parse(source, format="xml")
    module = Graph()
    classes = set(map(URIRef, record["classes"]))
    for subject in classes:
        for predicate, obj in original.predicate_objects(subject):
            if (
                isinstance(obj, Literal)
                or (predicate == RDF.type and obj == OWL.Class)
                or (predicate == RDFS.subClassOf and obj in classes)
            ):
                module.add((subject, predicate, obj))
    module.add((MODULE, RDF.type, OWL.Ontology))
    module.add((MODULE, DCT.source, URIRef(record["ontology_versions"][0])))
    module.add(
        (MODULE, DCT.license, URIRef("https://creativecommons.org/licenses/by/4.0/"))
    )
    module.add(
        (
            MODULE,
            DCT.description,
            Literal(
                "Asserted named-ancestor extract only; not the full FoodOn ontology. Attribution: FoodOn consortium."
            ),
        )
    )
    module.serialize(HERE / "foodon-module.ttl", format="turtle")
    print(f"Verified source; wrote {len(module)} module triples.")


if __name__ == "__main__":
    main()
