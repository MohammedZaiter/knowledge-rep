"""Course Session 7 show_prompt.py. Prints the exact FoodScope rules, VoID schema and selected examples without calling Gemini."""

import sys

from access_layer import build_prompt, load_examples, pick_examples, schema_text


def main():
    question = " ".join(sys.argv[1:]) or "How many foods are there?"
    shots = pick_examples(question, load_examples())
    prompt = build_prompt(question, schema_text(), shots)
    print(prompt)
    print("\n" + "-" * 60)
    print(
        f"examples picked: {', '.join(e['id'] for e in shots)}  ({', '.join(e['question'] for e in shots)})"
    )
    print(f"prompt: {len(prompt):,} characters, {len(prompt.splitlines())} lines")


if __name__ == "__main__":
    main()
