"""Run this checkout's code, not whichever checkout the shared Python environment was installed from.

The one environment (tools/setup-python.ps1) installs Rostrum's packages "editable" from a single checkout, so a team
worktree's tests and screens silently ran the main checkout's code (and looked for FFmpeg there). Entry points
(the root conftest.py, each app's screen/main.py) call use_this_checkout() first; it also sets PYTHONPATH so servers
and jobs they start run the same code. The package list matches tools/setup-python.ps1.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE_DIRS = ("shared/core", "shared/gui-kit", "shared/painting-kit", "shared/mcp",
                "apps/2d/python", "apps/sound/python", "apps/3d/python")


def use_this_checkout() -> None:
    dirs = [str(ROOT / d) for d in PACKAGE_DIRS]
    sys.path[:0] = [d for d in dirs if d not in sys.path]
    old = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p and p not in dirs]
    os.environ["PYTHONPATH"] = os.pathsep.join(dirs + old)
