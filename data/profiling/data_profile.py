"""Profile prepared CSV tables and record evidence for proposed SHACL rules.

    python data/profiling/data_profile.py

Counts each rule of the constraint inventory on the prepared tables and
writes data/constraint_inventory.csv, one row per rule with the count that supports it and where the count came from.
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data.prepare import NUTRIENTS, read_csv

DATA = ROOT / "data"
BUILD = ROOT / "build"


def profile():
    """Measure source data without changing it or filling missing observations."""
    foods = read_csv(DATA / "foods.csv")
    observations = read_csv(DATA / "measurements.csv")
    categories = read_csv(DATA / "categories.csv")
    nutrients = read_csv(DATA / "nutrients.csv")

    food_ids = {row["fdc_id"] for row in foods}
    category_ids = {row["id"] for row in categories}
    nutrient_ids = {row["nutrient_id"] for row in nutrients}
    counts = Counter(row["food_id"] for row in observations)
    pairs = {(row["food_id"], row["nutrient_id"]) for row in observations}
    grams = sum(NUTRIENTS[row["nutrient_id"]][1] == "G" for row in observations)
    rules = [
        (
            "C1",
            "Unique nonempty food identifiers",
            len(foods)
            - len(food_ids)
            + sum(not row["fdc_id"].strip() for row in foods),
            "foods.fdc_id",
            "Violation",
            len(foods),
            "foods",
        ),
        (
            "C2",
            "A nonempty description for each food",
            sum(not row["description"].strip() for row in foods),
            "foods.description",
            "Violation",
            len(foods),
            "foods",
        ),
        (
            "C3",
            "Every category reference resolves",
            sum(row["food_category_id"] not in category_ids for row in foods),
            "foods -> categories",
            "Violation",
            len(foods),
            "foods",
        ),
        (
            "C4",
            "Nutrient quantities are nonnegative",
            sum(float(row["amount"]) < 0 for row in observations),
            "measurements.amount",
            "Violation",
            len(observations),
            "observations",
        ),
        (
            "C5",
            "One amount for each food and selected nutrient",
            len(observations) - len(pairs),
            "measurements(food_id,nutrient_id)",
            "Violation",
            len(observations),
            "observations",
        ),
        (
            "C6",
            "Gram amounts do not exceed 100 g per 100 g",
            sum(
                NUTRIENTS[row["nutrient_id"]][1] == "G" and float(row["amount"]) > 100
                for row in observations
            ),
            "measurements + nutrient unit",
            "Violation",
            grams,
            "gram observations",
        ),
        (
            "C7",
            "Each food has all six selected nutrient observations",
            sum(counts[food_id] < len(NUTRIENTS) for food_id in food_ids),
            "foods -> measurements",
            "Warning",
            len(food_ids),
            "foods",
        ),
        (
            "C8",
            "Observation references an existing food and nutrient",
            sum(
                row["food_id"] not in food_ids or row["nutrient_id"] not in nutrient_ids
                for row in observations
            ),
            "measurements.food_id, measurements.nutrient_id",
            "Violation",
            len(observations),
            "observations",
        ),
        (
            "C9",
            "Each food has one publication date",
            sum(not row["publication_date"].strip() for row in foods),
            "foods.publication_date",
            "Violation",
            len(foods),
            "foods",
        ),
        (
            "C10",
            "Each nutrient and category has a nonempty name; nutrient units are G or MG",
            sum(
                not row["name"].strip() or row["unit"] not in {"G", "MG"}
                for row in nutrients
            )
            + sum(not row["description"].strip() for row in categories),
            "nutrients.name, nutrients.unit, categories.description",
            "Violation",
            len(nutrients) + len(categories),
            "reference rows",
        ),
    ]
    rule_fields = [
        "id",
        "rule",
        "evidence_in_data",
        "exceptions",
        "source_column_or_table",
        "severity",
    ]
    rules = [
        (rid, rule, f"{n:,} of {total:,} {unit} break it", n, where, severity)
        for rid, rule, n, where, severity, total, unit in rules
    ]
    report = {
        "foods": len(foods),
        "observations": len(observations),
        "publication_dates": dict(Counter(row["publication_date"] for row in foods)),
        "missing_by_nutrient": {
            nutrient_id: len(
                food_ids
                - {
                    row["food_id"]
                    for row in observations
                    if row["nutrient_id"] == nutrient_id
                }
            )
            for nutrient_id in NUTRIENTS
        },
        "rules": [dict(zip(rule_fields, rule)) for rule in rules],
    }
    BUILD.mkdir(exist_ok=True)
    (BUILD / "profile.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (DATA / "constraint_inventory.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(rule_fields)
        writer.writerows(rules)
    return report


def main():
    print(json.dumps(profile(), indent=2))


if __name__ == "__main__":
    main()
