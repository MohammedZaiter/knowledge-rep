"""Course Session 7 record_llm.py adapted to FoodScope questions. Calls the configured Gemini model and saves genuine replies and evaluations under build/access. Requires GOOGLE_API_KEY; no synthetic recordings are supplied."""

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from access_layer import RULES_ID

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "build" / "access"
RUNS = [
    ("ask-foods.txt", ["ask.py", "How many foods are there?"]),
    ("ask-price.txt", ["ask.py", "What is the price of each food?"]),
    ("evaluate.txt", ["evaluate.py"]),
]


def main():
    env = dict(
        os.environ, LLM_MODE="record", LLM_DELAY=os.environ.get("LLM_DELAY", "4")
    )
    OUT.mkdir(parents=True, exist_ok=True)
    for name, args in RUNS:
        print(f"recording {name} ...", flush=True)
        r = subprocess.run(
            [sys.executable, *args], cwd=HERE, env=env, capture_output=True, text=True
        )
        if r.returncode:
            sys.exit(f"{name} failed:\n{r.stderr[-2000:]}")
        head = (
            f"python {' '.join(args)}   (recorded {date.today()}, model "
            f"{os.environ.get('LLM_MODEL', 'gemini-3.5-flash-lite')}, rules {RULES_ID})\n"
        )
        (OUT / name).write_text(head + r.stdout)
        print(r.stdout.splitlines()[-1] if r.stdout else "", flush=True)
    print("done: reference-outputs/llm-cache.json and the four outputs. Commit them.")


if __name__ == "__main__":
    main()
