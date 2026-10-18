"""Build the template SQL sample from the committed USDA CSVs, without inventing rows."""

import csv
import sqlite3
from pathlib import Path

DATA = Path(__file__).resolve().parent


def write_sample():
    with sqlite3.connect(":memory:") as con:
        for name in ("foods", "measurements", "nutrients", "categories"):
            with (DATA / f"{name}.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                reader = csv.DictReader(stream)
                columns = reader.fieldnames
                definitions = ", ".join(f'"{column}" TEXT' for column in columns)
                con.execute(f'CREATE TABLE "{name}" ({definitions})')
                placeholders = ", ".join("?" for _ in columns)
                con.executemany(
                    f'INSERT INTO "{name}" VALUES ({placeholders})',
                    [[row[column] or None for column in columns] for row in reader],
                )
        (DATA / "example.sql").write_text(
            "\n".join(con.iterdump()) + "\n", encoding="utf-8"
        )
    print("Wrote data/example.sql from the four prepared USDA tables.")


if __name__ == "__main__":
    write_sample()
