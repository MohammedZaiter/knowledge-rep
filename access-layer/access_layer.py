"""Your team's access layer (from the course's Session 7 lab): a question in
English becomes a SPARQL query over your own graph.

YOUR TEAM changes three things: NS and PFX below (your ontology's namespace
and prefix), prompt_rules.txt (how things are named in your data), and the
examples and test questions (examples.ttl, questions.yaml).

Five small parts, each a function you can read on its own:

  schema_text     what the graph holds, read from its VoID description
  pick_examples   the 3 example queries whose questions share most words
  ask_model       one call to the language model (live, recorded or replayed)
  check_query     is the query valid SPARQL, and does it use only real terms?
  answer          the whole loop: ask, check, repair up to 2 times, or refuse

The model is Gemini, with the key GOOGLE_API_KEY from .env; LLM_MODEL picks
which Gemini model. LLM_MODE=record saves each answer in llm-cache.json, and
LLM_MODE=replay answers from it: record your test run, and your score can be
reproduced without the network.
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path

import pyoxigraph as ox
import requests
from dotenv import load_dotenv
from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.plugins.sparql import prepareQuery

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
load_dotenv(ROOT / ".env")
# ---- YOUR TEAM: your ontology's namespace and the prefix the model should use
NS = "https://ul.edu.lb/kr/food#"
PFX = "food"
# ----
GRAPH = ROOT / "build" / "reasoned.ttl"
VOID_FILE = Path(os.environ.get("VOID_FILE", ROOT / "build" / "void.ttl"))
EXAMPLES = HERE / "examples.ttl"
CACHE = HERE / "llm-cache.json"
DATASET = URIRef("https://ul.edu.lb/kr/foodscope/void")
UL = NS
VOID = Namespace("http://rdfs.org/ns/void#")
VEXT = Namespace("http://ldf.fi/void-ext#")
SH = Namespace("http://www.w3.org/ns/shacl#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai"  # Gemini's OpenAI style address
PREFIXES = (
    f"PREFIX {PFX}: <{NS}>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
)


# ---------------------------------------------------------------- the graph
def open_store(path=GRAPH):
    """The graph to ask. With SPARQL_ENDPOINT set (in the stack:
    http://fuseki:3030/kr/sparql), that address; otherwise the pipeline's
    build/graph.nt loaded in memory: the same data."""
    endpoint = os.environ.get("SPARQL_ENDPOINT")
    if endpoint:
        return endpoint
    store = ox.Store()
    store.bulk_load(
        path=str(path),
        format=ox.RdfFormat.N_TRIPLES
        if str(path).endswith(".nt")
        else ox.RdfFormat.TURTLE,
    )
    ontology = (
        ROOT / "ontology" / "ontology.ttl"
    )  # as in the endpoint: the data and the ontology
    if ontology.exists():
        store.bulk_load(path=str(ontology), format=ox.RdfFormat.TURTLE)
    return store


def with_prefixes(query):
    return query if f"PREFIX {PFX}:" in query else PREFIXES + query


def run(store, query):
    """Run a SELECT or ASK query; returns a list of rows (dicts of strings) or True/False."""
    if isinstance(store, str):  # a SPARQL endpoint over HTTP
        r = requests.post(
            store,
            data={"query": with_prefixes(query)},
            timeout=60,
            headers={"Accept": "application/sparql-results+json"},
        )
        r.raise_for_status()
        res = r.json()
        if "boolean" in res:
            return res["boolean"]
        return [
            {k: v["value"] for k, v in b.items()} for b in res["results"]["bindings"]
        ]
    res = store.query(with_prefixes(query))
    if isinstance(res, bool):
        return res
    names = [v.value for v in res.variables]
    return [{n: row[n].value for n in names if row[n] is not None} for row in res]


# ---------------------------------------------------------------- schema, from VoID
def load_void(path=VOID_FILE):
    """{class: number of things}, and {property: {class: [target classes or datatypes]}}."""
    g = Graph().parse(path)
    classes, props = {}, {}
    for part in g.objects(DATASET, VOID.classPartition):
        c = str(g.value(part, VOID["class"]))
        classes[c] = int(g.value(part, VOID.entities))
        for pp in g.objects(part, VOID.propertyPartition):
            targets = [
                str(g.value(o, VOID["class"]))
                for o in g.objects(pp, VOID.classPartition)
            ]
            targets += [
                str(g.value(o, VEXT.datatype))
                for o in g.objects(pp, VEXT.datatypePartition)
            ]
            props.setdefault(str(g.value(pp, VOID.property)), {})[c] = targets
    return classes, props


def short(iri):
    return iri.replace(UL, f"{PFX}:").replace(
        "http://www.w3.org/2001/XMLSchema#", "xsd:"
    )


def schema_text(path=VOID_FILE):
    """The schema in a few lines of plain text, for the prompt."""
    classes, props = load_void(path)
    lines = [
        f"{short(c)} ({n:,} things)"
        for c, n in sorted(classes.items(), key=lambda x: (-x[1], x[0]))
    ]
    for p, by_class in sorted(props.items()):
        for c, targets in sorted(by_class.items()):
            lines.append(
                f"{short(c)} {short(p)} {' or '.join(short(t) for t in targets)}"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------- example queries
def load_examples(path=EXAMPLES):
    """Examples in the SHACL vocabulary: rdfs:comment holds the question, sh:select the query."""
    g = Graph().parse(path)
    out = [
        {
            "id": str(ex).rsplit("/", 1)[-1],
            "question": str(g.value(ex, RDFS.comment)),
            "query": str(g.value(ex, SH.select)),
        }
        for ex in g.subjects(RDF.type, SH.SPARQLExecutable)
    ]
    return sorted(out, key=lambda e: e["id"])


STOP = {
    "the",
    "a",
    "an",
    "of",
    "is",
    "are",
    "which",
    "what",
    "how",
    "many",
    "does",
    "do",
    "did",
    "in",
    "by",
    "to",
    "there",
    "with",
    "their",
    "each",
    "and",
}


def words(text):
    return set(re.findall(r"[a-z0-9_]+", text.lower())) - STOP


def pick_examples(question, examples, k=3):
    """The k examples whose questions share the most words with this one (ties: file order)."""
    q = words(question)
    return sorted(examples, key=lambda e: -len(q & words(e["question"])))[:k]


# ---------------------------------------------------------------- the prompt and the model
RULES = (HERE / "prompt_rules.txt").read_text().strip()
RULES_ID = hashlib.sha256(RULES.encode()).hexdigest()[
    :8
]  # recorded outputs name the rules they were made with


def build_prompt(question, schema, examples, hints=None):
    parts = [
        RULES,
        "",
        "Schema (the classes, then: class property target):",
        schema,
        "",
    ]
    if examples:
        parts.append("Examples:")
        for e in examples:
            parts += [f"Question: {e['question']}", e["query"].strip(), ""]
    if hints:
        parts += [
            "Your previous query had these problems. Write it again without them:"
        ]
        parts += [f"- {h}" for h in hints] + [""]
    parts.append(f"Question: {question}")
    return "\n".join(parts)


def model_name():
    return os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")


def prompt_key(prompt):
    return hashlib.sha256(f"{model_name()}\n{prompt}".encode()).hexdigest()[:16]


def ask_model(prompt, mode=None):
    """One call. LLM_MODE live (default): ask the model. record: ask and save the answer.
    replay: return the saved answer for exactly this prompt and model."""
    mode = mode or os.environ.get("LLM_MODE", "live")
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    key = prompt_key(prompt)
    if mode == "replay":
        if key not in cache:
            raise SystemExit(
                f"No recorded answer for this prompt (key {key}). Replay works only for the "
                "lab's own questions and files, unchanged; run live for anything else."
            )
        return cache[key]["reply"]
    base = GEMINI
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit(
            "No key: put GOOGLE_API_KEY in  .env (see  .env.example), "
            "or run with LLM_MODE=replay."
        )
    # A free tier limits requests per minute, tokens per minute and requests per
    # day, per project. Wait between calls (4 s keeps under 15 a minute), and
    # on "too many requests" (429) wait longer and try again.
    time.sleep(float(os.environ.get("LLM_DELAY", "4")))
    for attempt in range(4):
        try:
            r = requests.post(
                f"{base}/chat/completions",
                timeout=90,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model_name(),
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        except requests.ConnectionError:
            raise SystemExit(
                f"Cannot reach the model at {base}. Check the connection, or run with LLM_MODE=replay."
            )
        if r.status_code != 429:
            break
        if "PerDay" in r.text or "per day" in r.text.lower():
            raise SystemExit(
                "The free tier's daily limit is used up for this project (it resets at midnight "
                "Pacific time, 10:00 in Beirut). Run with LLM_MODE=replay, or use another "
                "Gemini model (LLM_MODEL)."
            )
        wait = 20 * (attempt + 1)
        print(
            f"  (too many requests a minute: waiting {wait} s, then trying again)",
            flush=True,
        )
        time.sleep(wait)
    if r.status_code == 429:
        raise SystemExit(
            "Still too many requests after four tries. Wait a minute, set LLM_DELAY=8, "
            "or run with LLM_MODE=replay."
        )
    if r.status_code in (400, 401, 403):
        raise SystemExit(
            f"The model refused the key or the request ({r.status_code}): {r.text[:200]}\n"
            "Check GOOGLE_API_KEY in  .env, or run with LLM_MODE=replay."
        )
    r.raise_for_status()
    reply = r.json()["choices"][0]["message"]["content"]
    if mode == "record":
        cache[key] = {"model": model_name(), "reply": reply}
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True))
    return reply


def clean(reply):
    """The query inside a reply, without Markdown fences."""
    m = re.search(r"```(?:sparql|SPARQL)?\s*(.*?)```", reply, re.S)
    return (m.group(1) if m else reply).strip()


# ---------------------------------------------------------------- the check
def ul_terms(query):
    """Local names of every term of your namespace the query uses, prefixed or written in full."""
    return set(re.findall(rf"\b{PFX}:([A-Za-z_]\w*)", query)) | set(
        re.findall(rf"<{re.escape(NS)}(\w+)>", query)
    )


def unknown_properties(query, classes, props):
    """Problems: properties of your namespace the query uses that the graph does not have."""
    known = {p[len(NS) :] for p in props}
    used = {t for t in ul_terms(query) if t[0].islower()}
    listed = ", ".join(sorted(f"{PFX}:" + k for k in known))
    return [
        f"{PFX}:{t} is not a property of this graph. The properties are: {listed}"
        for t in sorted(used - known)
    ]


def unknown_classes(query, classes, props):
    """Problems: classes of your namespace the query uses that the graph does not have."""
    known = {c[len(NS) :] for c in classes}
    used = {t for t in ul_terms(query) if t[0].isupper()}
    listed = ", ".join(sorted(f"{PFX}:" + k for k in known))
    return [
        f"{PFX}:{t} is not a class of this graph. The classes are: {listed}"
        for t in sorted(used - known)
    ]


CHECKS = [unknown_properties, unknown_classes]


def check_query(query, void_path=VOID_FILE, checks=None):
    """A list of problems in plain English; an empty list means the query may be run."""
    try:
        prepareQuery(with_prefixes(query))
    except Exception as e:
        return [f"not valid SPARQL: {str(e).splitlines()[0][:150]}"]
    classes, props = load_void(void_path)
    return [p for check in (checks or CHECKS) for p in check(query, classes, props)]


# ---------------------------------------------------------------- the loop
def answer(
    question,
    store,
    examples,
    use_examples=True,
    repair=True,
    checks=None,
    mode=None,
    tries=3,
):
    """Returns {query, rows, refused, attempts}. attempts lists each query tried and its problems.
    repair=False: one try, run as written, no check (what a model alone gives you)."""
    schema = schema_text()
    shots = pick_examples(question, examples) if use_examples else []
    hints, attempts = None, []
    for _ in range(tries if repair else 1):
        reply = ask_model(build_prompt(question, schema, shots, hints), mode)
        if reply.strip().upper().startswith("REFUSE"):
            return {
                "query": None,
                "rows": None,
                "refused": reply.strip(),
                "attempts": attempts,
            }
        query = clean(reply)
        problems = check_query(query, checks=checks) if repair else []
        if not problems:
            try:
                rows = run(store, query)
                attempts.append({"query": query, "problems": []})
                return {
                    "query": with_prefixes(query),
                    "rows": rows,
                    "refused": None,
                    "attempts": attempts,
                }
            except Exception as e:
                problems = [f"the endpoint rejected it: {str(e).splitlines()[0][:150]}"]
        attempts.append({"query": query, "problems": problems})
        hints = problems
    if (
        not repair
    ):  # no check and no repair: the broken query is the answer, and it answers nothing
        return {
            "query": with_prefixes(attempts[-1]["query"]),
            "rows": None,
            "refused": None,
            "attempts": attempts,
        }
    return {
        "query": None,
        "rows": None,
        "attempts": attempts,
        "refused": f"REFUSE: no valid query after {len(attempts)} tries",
    }
