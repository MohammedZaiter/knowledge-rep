"""Course Session 5 setup_ontop.py. Downloads Ontop 5.5.0 and PostgreSQL JDBC 42.7.13 from the original course URLs. Requires Java 21; local credentials and flattened vocabulary are prepared from root .env."""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
CLI_URL = (
    "https://github.com/ontop/ontop/releases/download/ontop-5.5.0/ontop-cli-5.5.0.zip"
)
JDBC_URL = "https://github.com/pgjdbc/pgjdbc/releases/download/REL42.7.13/postgresql-42.7.13.jar"
CLI_DIR = HERE / "ontop-cli"


def download(url, dest):
    print(f"downloading {url.rsplit('/', 1)[-1]} ...")
    with urlopen(url, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def main():
    from connection import java_environment, write_properties

    java_environment()
    write_properties()
    if shutil.which("java") is None:
        sys.exit(
            "Java not found. Install the JDK 21 (demos/README.md, Session 1) and open a new terminal."
        )
    print(
        subprocess.run(
            ["java", "-version"], capture_output=True, text=True
        ).stderr.splitlines()[0]
    )
    if not (CLI_DIR / "ontop").exists():
        z = HERE / "ontop-cli.zip"
        download(CLI_URL, z)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(CLI_DIR)
        z.unlink()
        (CLI_DIR / "ontop").chmod(0o755)
    jar = CLI_DIR / "jdbc" / JDBC_URL.rsplit("/", 1)[-1]
    if not jar.exists():
        jar.parent.mkdir(exist_ok=True)
        download(JDBC_URL, jar)
    print(f"ready: {CLI_DIR.relative_to(HERE.parent)} with {jar.name}")


if __name__ == "__main__":
    main()
