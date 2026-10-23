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
PACKAGES = ("rostrum_core", "rostrum_gui", "rostrum_paint", "rostrum_connect",
            "rostrum2d", "rostrum_sound", "rostrum3d")


def use_this_checkout() -> None:
    dirs = [str(ROOT / d) for d in PACKAGE_DIRS]
    sys.path[:0] = [d for d in dirs if d not in sys.path]
    old = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p and p not in dirs]
    os.environ["PYTHONPATH"] = os.pathsep.join(dirs + old)


def check_this_checkout() -> None:
    """Fail loudly when a package would load from another checkout (a test run that silently tests main's code)."""
    import importlib.util
    for name in PACKAGES:
        spec = importlib.util.find_spec(name)
        if spec is not None and spec.origin and ROOT not in Path(spec.origin).resolve().parents:
            raise RuntimeError(f"{name} loads from {spec.origin}, not this checkout ({ROOT}). "
                               "Run pytest from this checkout so its conftest.py applies (no per-package pytest settings).")
