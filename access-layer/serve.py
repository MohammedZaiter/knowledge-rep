"""Course Session 7 serve.py TEXT2SPARQL GET contract, extended to serve the FoodScope static UI and /api/ask result rows. Same question/dataset validation and refusal-as-empty-query contract; API failures return HTTP 503."""

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from access_layer import answer, load_examples, open_store

DATASET = "https://ul.edu.lb/kr/foodscope/"
STORE, EXAMPLES = open_store(), load_examples()


def query_for(question):
    r = answer(question, STORE, EXAMPLES)
    if r["refused"]:
        reason = r["refused"].replace("\n", " ")
        return f"# {reason}\nSELECT * WHERE {{ FILTER(false) }}"
    return r["query"]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(
            *args,
            directory=directory or str(Path(__file__).resolve().parents[1]),
            **kwargs,
        )

    def send_head(self):
        # The UI needs public project files; local .env and .git are never web assets.
        if any(
            part.startswith(".")
            for part in Path(unquote(urlparse(self.path).path)).parts
        ):
            self.send_error(404)
            return None
        return super().send_head()

    def do_GET(self):
        args = parse_qs(urlparse(self.path).query)
        if urlparse(self.path).path != "/api/ask" and "question" not in args:
            return super().do_GET()
        question, dataset = (
            args.get("question", [""])[0],
            args.get("dataset", [DATASET])[0],
        )
        if not question or dataset != DATASET:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(
                b'{"error": "give ?question=... and dataset=https://ul.edu.lb/kr/foodscope/"}'
            )
            return
        try:
            result = answer(question, STORE, EXAMPLES)
        except (SystemExit, Exception) as error:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(error)}).encode())
            return
        query = result["query"]
        if result["refused"]:
            reason = result["refused"].replace("\n", " ")
            query = f"# {reason}\nSELECT * WHERE {{ FILTER(false) }}"
        body = json.dumps(
            {"dataset": dataset, "question": question, **result, "query": query}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("  " + fmt % args)


def main():
    host, port = (
        os.environ.get("HOST", "127.0.0.1"),
        int(os.environ.get("PORT", "8000")),
    )
    print(
        f"serving the TEXT2SPARQL contract on http://{host}:{port}/?question=...&dataset={DATASET}"
    )
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
