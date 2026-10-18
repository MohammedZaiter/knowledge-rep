# ruff: noqa: E402
"""Behavior checks for the course-derived gate and access-layer contracts."""

import csv
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "access-layer"))
sys.path.insert(0, str(ROOT / "model"))
import access_layer as access
import numpy as np
import pyoxigraph as ox
from learning_utils import split_by_category
from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace

import run

FOOD = run.FOOD
BASE = Namespace("https://ul.edu.lb/kr/id/test/")


def sample_graph():
    graph = Graph()
    graph.add((BASE.food, RDF.type, FOOD.Food))
    graph.add((BASE.food, FOOD.sourceId, Literal("1", datatype=XSD.string)))
    graph.add((BASE.food, FOOD.name, Literal("Test food", datatype=XSD.string)))
    graph.add(
        (
            BASE.food,
            FOOD.publishedOn,
            Literal("2024-01-01T00:00:00", datatype=XSD.dateTime),
        )
    )
    graph.add((BASE.food, FOOD.category, BASE.category))
    graph.add((BASE.category, RDF.type, FOOD.Category))
    graph.add((BASE.category, FOOD.name, Literal("Test category")))
    for index in range(6):
        obs, nutrient = BASE[f"obs{index}"], BASE[f"nutrient{index}"]
        for triple in [
            (BASE.food, FOOD.hasObservation, obs),
            (obs, RDF.type, FOOD.Observation),
            (obs, FOOD.ofFood, BASE.food),
            (obs, FOOD.nutrient, nutrient),
            (obs, FOOD.amount, Literal("1", datatype=XSD.decimal)),
            (nutrient, RDF.type, FOOD.Nutrient),
            (nutrient, FOOD.name, Literal(f"Nutrient {index}")),
            (nutrient, FOOD.unit, Literal("G")),
        ]:
            graph.add(triple)
    return graph


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = patch.object(run, "BUILD", Path(self.temp.name))
        self.output.start()

    def tearDown(self):
        self.output.stop()
        self.temp.cleanup()

    def test_good_graph_passes(self):
        run.validate_graph(sample_graph())

    def test_warning_does_not_fail(self):
        graph = sample_graph()
        graph.remove((BASE.food, FOOD.hasObservation, BASE.obs0))
        run.validate_graph(graph)
        self.assertIn("Warning", (run.BUILD / "validation.txt").read_text())

    def test_negative_amount_fails(self):
        graph = sample_graph()
        graph.set((BASE.obs0, FOOD.amount, Literal("-1", datatype=XSD.decimal)))
        with self.assertRaisesRegex(ValueError, "SHACL gate failed"):
            run.validate_graph(graph)

    def test_empty_target_fails(self):
        graph = sample_graph()
        graph.remove((None, RDF.type, FOOD.Nutrient))
        with self.assertRaisesRegex(ValueError, "no focus nodes"):
            run.validate_graph(graph)

    def test_imports_resolve_offline(self):
        graph = run.merged_graph(ROOT / "ontology/ontology.ttl")
        obo = Namespace("http://purl.obolibrary.org/obo/")
        self.assertIn((FOOD.Food, RDFS.subClassOf, obo.FOODON_00001002), graph)
        self.assertIn(
            (obo.FOODON_00001002, RDFS.subClassOf, obo.FOODON_00002403), graph
        )


class TemplateSourceTests(unittest.TestCase):
    def test_sql_sample_matches_all_four_csv_tables(self):
        with sqlite3.connect(":memory:") as connection:
            connection.executescript((ROOT / "data/example.sql").read_text())
            for name in ("foods", "measurements", "nutrients", "categories"):
                with (ROOT / "data" / f"{name}.csv").open(
                    encoding="utf-8-sig", newline=""
                ) as stream:
                    reader = csv.DictReader(stream)
                    expected = [
                        tuple(row[column] or None for column in reader.fieldnames)
                        for row in reader
                    ]
                actual = connection.execute(f'SELECT * FROM "{name}"').fetchall()
                self.assertCountEqual(actual, expected)

    def test_gate_prevents_reasoning_endpoint_load_and_ui(self):
        graph = sample_graph()
        graph.set((BASE.obs0, FOOD.amount, Literal("-1", datatype=XSD.decimal)))
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(run, "BUILD", Path(temporary)),
            patch.object(
                sys,
                "argv",
                ["pipeline/run.py", "--skip-profile", "--skip-learning", "--ui"],
            ),
            patch.object(run, "profile", return_value={"foods": 1, "observations": 6}),
            patch.object(run, "source", return_value="sqlite:///:memory:"),
            patch.object(run, "materialize", return_value=graph),
            patch.object(run, "reason") as reason,
            patch.object(run, "load") as load,
            patch.object(run, "serve_ui") as serve,
        ):
            with self.assertRaisesRegex(ValueError, "SHACL gate failed"):
                run.main()
            reason.assert_not_called()
            load.assert_not_called()
            serve.assert_not_called()


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.store = ox.Store()
        self.store.load(
            input=sample_graph().serialize(format="nt"), format=ox.RdfFormat.N_TRIPLES
        )
        self.classes = {str(FOOD.Food): 1}
        self.props = {str(FOOD.name): {}}
        self.schema = patch.object(
            access, "schema_text", return_value="food:Food food:name xsd:string"
        )
        self.void = patch.object(
            access, "load_void", return_value=(self.classes, self.props)
        )
        self.schema.start()
        self.void.start()

    def tearDown(self):
        self.schema.stop()
        self.void.stop()

    def test_repair_loop_uses_course_checker(self):
        with patch.object(
            access,
            "ask_model",
            side_effect=[
                "SELECT ?x WHERE {?x food:invented ?v}",
                "SELECT ?name WHERE {?f a food:Food; food:name ?name}",
            ],
        ):
            result = access.answer("List food names", self.store, [])
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(result["rows"], [{"name": "Test food"}])

    def test_refusal_is_preserved(self):
        with patch.object(
            access, "ask_model", return_value="REFUSE: prices are absent"
        ):
            result = access.answer("What is the price?", self.store, [])
        self.assertTrue(result["refused"])
        self.assertIsNone(result["rows"])

    def test_unknown_class_check_is_course_solution(self):
        self.assertTrue(access.check_query("SELECT ?f WHERE {?f a food:Invented}"))

    def test_unknown_full_uri_is_rejected(self):
        self.assertTrue(
            access.check_query(
                "SELECT ?f WHERE {?f <https://ul.edu.lb/kr/food#invented> ?v}"
            )
        )

    def test_prompt_and_test_questions_do_not_overlap(self):
        from questions_utils import load_questions

        examples = {example["question"] for example in access.load_examples()}
        heldout = {
            q["question"] for q in load_questions(ROOT / "access-layer/questions.yaml")
        }
        self.assertFalse(examples & heldout)

    def test_gold_queries_execute_without_model(self):
        from questions_utils import load_questions
        from rdflib.plugins.sparql import prepareQuery

        for item in load_questions(ROOT / "access-layer/questions.yaml"):
            if not item["refuse"]:
                prepareQuery(item["gold"])


class SplitTests(unittest.TestCase):
    def test_categories_never_overlap(self):
        groups = np.repeat(np.arange(18), 3)
        for seed in range(5):
            train, test = split_by_category(groups, seed=seed)
            self.assertFalse(set(groups[train]) & set(groups[test]))


class HTTPTests(unittest.TestCase):
    def setUp(self):
        import serve

        self.api = serve
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def test_static_ui_and_api_contract(self):
        with urllib.request.urlopen(self.base + "/") as response:
            self.assertIn(b"Ask the food graph", response.read())
        result = {
            "query": "SELECT ?n WHERE {BIND(1 AS ?n)}",
            "rows": [{"n": "1"}],
            "refused": None,
            "attempts": [{"query": "SELECT ?n WHERE {BIND(1 AS ?n)}", "problems": []}],
        }
        with patch.object(self.api, "answer", return_value=result):
            with urllib.request.urlopen(
                self.base + "/api/ask?question=Count"
            ) as response:
                body = json.load(response)
        self.assertEqual(body["rows"], [{"n": "1"}])
        self.assertEqual(body["dataset"], "https://ul.edu.lb/kr/foodscope/")

    def test_configuration_failure_is_http_503(self):
        with patch.object(
            self.api,
            "answer",
            side_effect=SystemExit("Configure GOOGLE_API_KEY locally"),
        ):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(self.base + "/api/ask?question=Count")
        self.assertEqual(caught.exception.code, 503)

    def test_refusal_returns_course_empty_query(self):
        with patch.object(
            self.api,
            "answer",
            return_value={
                "query": None,
                "rows": None,
                "refused": "REFUSE: price missing",
                "attempts": [],
            },
        ):
            with urllib.request.urlopen(self.base + "/?question=Price") as response:
                body = json.load(response)
        self.assertIn("FILTER(false)", body["query"])

    def test_hidden_files_are_not_served(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.base + "/.env")
        self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
