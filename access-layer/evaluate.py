"""Score the access layer on the test set, in three settings, the way
TEXT2SPARQL scores it: for each question, the set of values the query
returns against the set the right query returns (precision, recall, F1).

    python evaluate.py                      the three settings
    python evaluate.py --setting repair     one setting only
    python evaluate.py --add-class-check    after Part B: the check also catches unknown classes
    python evaluate.py --questions my_questions.yaml   add your own questions

Settings: schema (the schema only), examples (plus the 3 closest example
queries), repair (plus the check and up to 2 repairs). A refusal scores 0 on
a question the graph can answer, and counts as right on one it cannot.
"""

import argparse
import importlib.util
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from access_layer import CHECKS, answer, load_examples, model_name, open_store, run
from questions_utils import load_questions
from score_utils import answer_set, set_f1

SETTINGS = {
    "schema": dict(use_examples=False, repair=False),
    "examples": dict(use_examples=True, repair=False),
    "repair": dict(use_examples=True, repair=True),
}


def evaluate(questions, store, examples, setting, checks, verbose=True):
    f1s, refused_right, refused_wrong, repaired, lines = [], 0, 0, 0, []
    for q in questions:
        r = answer(q["question"], store, examples, checks=checks, **SETTINGS[setting])
        tries = len(r["attempts"])
        repaired += tries > 1 and r["refused"] is None
        if q["refuse"]:
            ok = r["refused"] is not None
            refused_right += ok
            lines.append(
                f"  {q['id']:>2}  {'refused, right' if ok else 'answered, should refuse':24} {q['question']}"
            )
            continue
        if r["refused"]:
            refused_wrong += 1
            f1 = 0.0
        else:
            f1 = set_f1(answer_set(r["rows"]), answer_set(run(store, q["gold"])))
        f1s.append(f1)
        lines.append(
            f"  {q['id']:>2}  F1 {f1:.2f}  tries {tries}{'  refused' if r['refused'] else ''}".ljust(
                33
            )
            + q["question"]
        )
    n_refuse = sum(1 for q in questions if q["refuse"])
    summary = (
        f"{setting:9} mean F1 {statistics.fmean(f1s):.3f} on {len(f1s)} answerable questions; "
        f"refused {refused_right} of {n_refuse} it should; refused {refused_wrong} it should not; "
        f"{repaired} answered after a repair"
    )
    if verbose:
        print("\n".join(lines))
    print(summary)
    return statistics.fmean(f1s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setting", choices=list(SETTINGS))
    ap.add_argument("--add-class-check", action="store_true")
    ap.add_argument(
        "--class-check-from",
        default=str(Path(__file__).parent / "my_access.py"),
        help=argparse.SUPPRESS,
    )
    ap.add_argument("--questions", action="append", default=[])
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    checks = list(CHECKS)
    if a.add_class_check:
        spec = importlib.util.spec_from_file_location("my_access", a.class_check_from)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        checks.append(mod.unknown_classes)
    questions = load_questions(Path(__file__).parent / "questions.yaml")
    for extra in a.questions:
        questions += load_questions(extra)
    store, examples = open_store(), load_examples()
    print(
        f"model: {model_name()}; {len(questions)} questions; checks: {', '.join(c.__name__ for c in checks)}"
    )
    scores = {}
    for s in [a.setting] if a.setting else list(SETTINGS):
        print(f"\n{s}:")
        scores[s] = evaluate(questions, store, examples, s, checks, verbose=not a.quiet)
    import os

    out = Path(__file__).resolve().parents[1] / "build" / "access"
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation.json").write_text(
        json.dumps(
            {
                "utc": datetime.now(timezone.utc).isoformat(),
                "model": model_name(),
                "mode": os.environ.get("LLM_MODE", "live"),
                "mean_f1": scores,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
