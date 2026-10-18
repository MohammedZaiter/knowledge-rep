"""Local UI shortcut; canonical pipeline entry point is pipeline/run.py."""

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.argv.extend(["--no-load", "--ui"])
    runpy.run_path(
        str(Path(__file__).resolve().parent / "pipeline/run.py"), run_name="__main__"
    )
