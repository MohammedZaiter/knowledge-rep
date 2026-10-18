"""Course Session 3 local_reasoner.py adapted to FoodScope. Resolves owl:imports through catalog-v001.xml and runs bundled HermiT via owlready2. A file stream fixes Windows file-URI loading; JAVA_EXE can specify Java 21."""

import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from dotenv import load_dotenv
from rdflib import OWL, Graph

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE
CATALOG = WORKSPACE / "catalog-v001.xml"
UL = "https://ul.edu.lb/kr/food#"
load_dotenv(HERE.parent / ".env")
if not os.environ.get("JAVA_EXE") and not shutil.which("java"):
    portable = next((HERE.parent / ".tools/java").glob("*/bin/java.exe"), None)
    if portable:
        os.environ["JAVA_EXE"] = str(portable)


def catalog_map(catalog=CATALOG):
    """IRI -> local file, read from the Protégé catalog (and the catalogs it names)."""
    ns = {"c": "urn:oasis:names:tc:entity:xmlns:xml:catalog"}
    found, todo, seen = {}, [catalog], set()
    while todo:
        cat = todo.pop()
        if cat in seen or not cat.exists():
            continue
        seen.add(cat)
        root = ET.parse(cat).getroot()
        for u in root.iter("{%s}uri" % ns["c"]):
            found.setdefault(u.get("name"), (cat.parent / u.get("uri")).resolve())
        for n in root.iter("{%s}nextCatalog" % ns["c"]):
            todo.append((cat.parent / n.get("catalog")).resolve())
    return found


def _parse(g, path):
    fmt = "turtle" if path.suffix == ".ttl" else "xml"
    g.parse(path, format=fmt)


def merged_graph(start):
    """One graph holding the start file and everything it imports, with no owl:imports left."""
    cmap = catalog_map()
    g, todo, done = Graph(), [Path(start).resolve()], set()
    while todo:
        path = todo.pop()
        if path in done:
            continue
        done.add(path)
        part = Graph()
        _parse(part, path)
        for _, _, imp in part.triples((None, OWL.imports, None)):
            key = str(imp)
            target = cmap.get(key) or cmap.get(key.rstrip("/#")) or cmap.get(key + "/")
            if target is None:
                raise SystemExit(
                    f"Import not found in the catalog: {key}. Run python fetch_ontologies.py first."
                )
            todo.append(target)
        part.remove((None, OWL.imports, None))
        g += part
    return g


def reason(start):
    """Load the start file with its imports into owlready2, run HermiT, return the world."""
    import owlready2

    if os.environ.get("JAVA_EXE"):
        owlready2.JAVA_EXE = os.environ["JAVA_EXE"]
    g = merged_graph(start)
    world = owlready2.World()
    with tempfile.TemporaryDirectory() as temporary:
        tmp = Path(temporary) / "merged.nt"
        g.serialize(tmp, format="nt", encoding="utf-8")
        with tmp.open("rb") as stream:
            onto = world.get_ontology(tmp.as_uri()).load(fileobj=stream)
    try:
        with onto:
            owlready2.sync_reasoner_hermit(world, infer_property_values=False, debug=0)
    except owlready2.OwlReadyInconsistentOntologyError:
        world.inconsistent = True
        return world
    world.inconsistent = False
    return world


def label(entity):
    """The English label if there is one, else the IRI's last part."""
    for lab in entity.label:
        return str(lab)
    return entity.iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def summary(world):
    """Impossible classes of ours, and the inferred classes of every individual of ours."""
    if world.inconsistent:
        return {"inconsistent": True, "impossible": [], "types": {}}
    impossible = sorted(
        label(c) for c in world.inconsistent_classes() if c.iri.startswith(UL)
    )
    types = {}
    for ind in world.individuals():
        if ind.iri.startswith(UL) or "/kr/id/" in ind.iri:
            types[label(ind)] = sorted(label(c) for c in ind.is_a if hasattr(c, "iri"))
    return {"inconsistent": False, "impossible": impossible, "types": types}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    s = summary(reason(sys.argv[1]))
    if s["inconsistent"]:
        print(
            "The ontology is inconsistent: it contradicts itself, so every answer is worthless."
        )
    print(
        "Impossible classes (equivalent to owl:Nothing):",
        ", ".join(s["impossible"]) or "none",
    )
    for name, cls in sorted(s["types"].items()):
        print(f"  {name}: {', '.join(cls)}")
