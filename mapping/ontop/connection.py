"""Configuration adapter for the course PostgreSQL/Ontop scripts; no credentials in source."""

import importlib
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def database_url():
    if os.environ.get("DB_URL"):
        return os.environ["DB_URL"]
    return URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("POSTGRES_USER", "kr"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        host="127.0.0.1",
        port=5432,
        database="foodscope",
    ).render_as_string(hide_password=False)


def java_environment():
    sys.path.insert(0, str(ROOT))
    importlib.import_module("ontology.local_reasoner")
    java = os.environ.get("JAVA_EXE")
    if java:
        os.environ["PATH"] = (
            str(Path(java).parent) + os.pathsep + os.environ.get("PATH", "")
        )


def write_properties():
    url = make_url(database_url())
    if not url.drivername.startswith("postgresql"):
        raise SystemExit(
            "The course Ontop path requires PostgreSQL; set DB_URL accordingly."
        )
    if not url.password:
        raise SystemExit(
            "Set POSTGRES_PASSWORD or DB_URL in the root .env for the optional integration comparison."
        )
    out = ROOT / "build/ontop"
    out.mkdir(parents=True, exist_ok=True)
    (out / ".food.properties").write_text(
        f"jdbc.url=jdbc:postgresql://{url.host}:{url.port or 5432}/{url.database}\njdbc.user={url.username}\njdbc.password={url.password}\njdbc.driver=org.postgresql.Driver\n"
    )
    sys.path.insert(0, str(ROOT))
    from ontology.local_reasoner import merged_graph

    merged_graph(ROOT / "ontology/ontology.ttl").serialize(
        out / "ontology.ttl", format="turtle"
    )
