"""Requested FoodScope UI adapter; course processing is in pipeline/run.py."""

import runpy
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    subprocess.run(
        [sys.executable, str(root / "pipeline/run.py"), "--no-load"],
        check=True,
    )
    sys.path.insert(0, str(root / "access-layer"))
    runpy.run_path(str(root / "access-layer/serve.py"), run_name="__main__")
