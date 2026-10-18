"""Prepare compact project CSVs from the downloaded USDA Foundation release."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NUTRIENTS = {
    "1003": ("protein", "G"),
    "1004": ("fat", "G"),
    "1005": ("carbohydrate", "G"),
    "1079": ("fiber", "G"),
    "1093": ("sodium", "MG"),
    "2000": ("sugars", "G"),
}


def read_csv(path):
    """Read a CSV as dictionaries, preserving source strings and zero amounts."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(name, rows):
    """Write a selected table to the project's data directory."""
    if not rows:
        raise ValueError(f"The selected table is empty: {name}")
    with (DATA / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prepare(source):
    """Select Foundation Foods and the six explicitly chosen nutrient definitions."""
    DATA.mkdir(exist_ok=True)
    foods = [
        row
        for row in read_csv(source / "food.csv")
        if row["data_type"] == "foundation_food"
    ]
    food_ids = {row["fdc_id"] for row in foods}
    nutrient_metadata = {row["id"]: row for row in read_csv(source / "nutrient.csv")}
    measurements = []

    for row in read_csv(source / "food_nutrient.csv"):
        if row["fdc_id"] not in food_ids or row["nutrient_id"] not in NUTRIENTS:
            continue
        if row["amount"] == "":
            continue
        nutrient_id = row["nutrient_id"]
        expected_unit = NUTRIENTS[nutrient_id][1]
        if nutrient_metadata[nutrient_id]["unit_name"] != expected_unit:
            raise ValueError(f"Unexpected unit for nutrient {nutrient_id}")
        measurements.append(
            {
                "measurement_id": row["id"],
                "food_id": row["fdc_id"],
                "nutrient_id": nutrient_id,
                "amount": row["amount"],
            }
        )

    write_csv("foods.csv", foods)
    write_csv("measurements.csv", measurements)
    write_csv("categories.csv", read_csv(source / "food_category.csv"))
    write_csv(
        "nutrients.csv",
        [
            {
                "nutrient_id": nutrient_id,
                "name": nutrient_metadata[nutrient_id]["name"],
                "unit": unit,
            }
            for nutrient_id, (_, unit) in NUTRIENTS.items()
        ],
    )
    manifest = {
        "source": "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_csv_2024-04-18.zip",
        "release": "April 2024 Foundation Foods",
        "license": "Public domain / CC0; attribution: USDA FoodData Central",
        "selection": "All foundation_food rows; six nutrient identifiers; amounts per 100 g edible portion",
        "foods": len(foods),
        "measurements": len(measurements),
        "source_csv_sha256": {
            name: hashlib.sha256((source / name).read_bytes()).hexdigest()
            for name in (
                "food.csv",
                "food_nutrient.csv",
                "nutrient.csv",
                "food_category.csv",
            )
        },
    }
    (DATA / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"Prepared {len(foods)} foods and {len(measurements)} observations.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, help="Extracted USDA folder containing food.csv"
    )
    args = parser.parse_args()
    source = args.source
    if source is None:
        candidates = sorted((DATA / "raw" / "usda").glob("*/food.csv"))
        if not candidates:
            parser.error(
                "Extract the USDA archive under data/raw/usda/, or pass --source PATH."
            )
        source = candidates[0].parent
    prepare(source)


if __name__ == "__main__":
    main()
