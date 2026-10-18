"""Profile prepared CSV tables and record evidence for proposed SHACL rules."""

import csv
import json
from collections import Counter
from pathlib import Path

from data.prepare import NUTRIENTS, read_csv

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
BUILD = ROOT / "build"


def profile():
    """Measure source data without changing it or filling missing observations."""
    foods = read_csv(DATA / "foods.csv")
    observations = read_csv(DATA / "measurements.csv")
    categories = read_csv(DATA / "categories.csv")
    
    food_ids = {row["fdc_id"] for row in foods}
    category_ids = {row["id"] for row in categories}
    counts = Counter(row["food_id"] for row in observations)
    pairs = {(row["food_id"], row["nutrient_id"]) for row in observations}
    rules = [
        (
            "C1",
            "Unique nonempty food identifiers",
            len(foods)
            - len(food_ids)
            + sum(not row["fdc_id"].strip() for row in foods),
            "foods.fdc_id",
            "Violation",
        ),
        (
            "C2",
            "A nonempty description for each food",
            sum(not row["description"].strip() for row in foods),
            "foods.description",
            "Violation",
        ),
        (
            "C3",
            "Every category reference resolves",
            sum(row["food_category_id"] not in category_ids for row in foods),
            "foods -> categories",
            "Violation",
        ),
        (
            "C4",
            "Nutrient quantities are nonnegative",
            sum(float(row["amount"]) < 0 for row in observations),
            "measurements.amount",
            "Violation",
        ),
        (
            "C5",
            "One amount for each food and selected nutrient",
            len(observations) - len(pairs),
            "measurements(food_id,nutrient_id)",
            "Violation",
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
        ),
        (
            "C7",
            "Each food has all six selected nutrient observations",
            sum(counts[food_id] < len(NUTRIENTS) for food_id in food_ids),
            "foods -> measurements",
            "Warning",
        ),
        (
            "C8",
            "Observation references an existing food",
            sum(row["food_id"] not in food_ids for row in observations),
            "measurements.food_id",
            "Violation",
        ),
    ]
    rule_fields = ["id", "rule", "exceptions", "evidence", "severity"]
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
    with (BUILD / "constraint_inventory.csv").open(
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
