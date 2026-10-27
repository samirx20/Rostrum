"""No app or kit module imports PySide6.QtTest at its top.

Every launch imports the step modules; a top-level QtTest import made a person's launch count as scripted
(rostrum_core.userhome.scripted), so the window opened frameless and behind and the settings went to a temp folder
(Sam, 2026-10-27, in all three apps since 2026-10-25). Step code takes QTest from rostrum_gui.lazy_qtest, or imports
it inside the function that uses it."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ["shared/gui-kit/rostrum_gui", "shared/core/rostrum_core", "apps/2d/screen/screen2d",
            "apps/sound/screen/screensound", "apps/3d/app/screen3d"]
MAINS = ["apps/2d/screen/main.py", "apps/sound/screen/main.py", "apps/3d/app/main.py"]


def _top_level_qtest(path: Path) -> bool:
    tree = ast.parse(path.read_bytes())          # bytes: Python reads the file's own encoding line
    for node in tree.body:                       # only the module's own top level: imports inside functions are fine
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("PySide6.QtTest"):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "PySide6" and any(a.name == "QtTest" for a in node.names):
            return True
        if isinstance(node, ast.Import) and any(a.name.startswith("PySide6.QtTest") for a in node.names):
            return True
    return False


def test_no_module_imports_qtest_at_its_top():
    files = [p for pkg in PACKAGES for p in (ROOT / pkg).rglob("*.py") if "tests" not in p.parts]
    files += [ROOT / m for m in MAINS]
    bad = [str(p.relative_to(ROOT)) for p in files if p.exists() and _top_level_qtest(p)]
    assert not bad, f"top-level QtTest import makes a person's launch scripted: {bad}"
