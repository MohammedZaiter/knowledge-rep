# ruff: noqa: E402
"""Course Session 5 load_database.py adapted to the four USDA CSVs. Uses the same pandas text-preserving frame and SQLAlchemy to_sql loader. Default target is the env-configured PostgreSQL source; --sqlite writes the local template database."""

import argparse
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(HERE / "ontop"))
from connection import database_url

SOURCE_TABLES = {
    name: ROOT / "data" / f"{name}.csv"
    for name in ("foods", "measurements", "nutrients", "categories")
}
POSTGRES_URL = database_url()
SQLITE_URL = f"sqlite:///{ROOT / 'build/example.sqlite'}"
TABLES = {name: name for name in SOURCE_TABLES}
TEXT_COLUMNS = str


def frame(key):
    df = pd.read_csv(SOURCE_TABLES[key], dtype=TEXT_COLUMNS)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    if key == "freight_rates":
        df.insert(0, "rate_id", range(1, len(df) + 1))
    return df


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--sqlite",
        action="store_true",
        help="write brunel.db here instead of using PostgreSQL",
    )
    url = SQLITE_URL if ap.parse_args().sqlite else POSTGRES_URL
    try:
        engine = create_engine(url)
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        sys.exit(
            "PostgreSQL is not answering on 127.0.0.1:5432. Start it with `docker compose up -d` "
            "in this folder, or run `python load_database.py --sqlite` to use a file instead."
        )
    for table, key in TABLES.items():
        df = frame(key)
        df.to_sql(table, engine, if_exists="replace", index=False)
        print(f"{table:<19} {len(df):>6,} rows  from {SOURCE_TABLES[key].name}")
    print(f"\nloaded into {url.split('@')[-1] if '@' in url else 'brunel.db'}")


if __name__ == "__main__":
    main()
