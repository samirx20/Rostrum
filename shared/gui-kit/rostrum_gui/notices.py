"""What the About / Licences screen shows: the app's name, version and the components it ships, with licences.

Installed app: the installer drops `notices.json` (and NOTICES.txt beside it); ROSTRUM_NOTICES points at the json.
Development checkout: made on the spot by tools/release/notices.py from this interpreter's site-packages and the
repo's ATTRIBUTIONS.md (the same generator the installer runs). 3D has no list yet: an empty but working screen."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sysconfig
import tempfile
from argparse import Namespace
from pathlib import Path

from PySide6.QtCore import Property, QObject

NAMES = {"2d": "Rostrum2D", "sound": "RostrumSound", "3d": "Rostrum3D", "editor": "Rostrum Editor"}
REPO = Path(__file__).resolve().parents[3]          # <repo>/shared/gui-kit/rostrum_gui/notices.py (or the install)
VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()   # the one version number (the installer's too)


def app_id(main_qml: Path | None = None) -> str:
    """ROSTRUM_APP, else the app folder in the main QML's path (apps/2d, apps/sound ...), else ''."""
    if os.environ.get("ROSTRUM_APP"):
        return os.environ["ROSTRUM_APP"]
    parts = Path(main_qml).resolve().parts if main_qml else ()
    return next((parts[i + 1] for i, p in enumerate(parts[:-1]) if p == "apps"), "")


def generate(app: str) -> dict:
    """Run the release generator on this interpreter's packages (development checkout only)."""
    tool = REPO / "tools" / "release" / "notices.py"
    attributions = REPO / "ATTRIBUTIONS.md"
    if app not in ("2d", "sound") or not tool.is_file() or not attributions.is_file():
        return {"items": [], "warnings": []}
    spec = importlib.util.spec_from_file_location("rostrum_release_notices", tool)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory(prefix="rostrum-notices-") as tmp:
        out = Path(tmp) / "notices.json"
        args = Namespace(app=app, attributions=str(attributions), site_packages=[sysconfig.get_paths()["purelib"]],
                         engine_deps=[str(REPO / "apps" / app / "engine" / "DEPENDENCIES.md")], out=str(out), text=None)
        with contextlib.redirect_stdout(io.StringIO()):
            failed = mod.build(args) != 0
        if failed:
            raise RuntimeError(f"notices for {app}: a shipped item has a GPL licence (see above)")
        return json.loads(out.read_text(encoding="utf-8"))


class Notices(QObject):
    def __init__(self, app: str, parent=None):
        super().__init__(parent)
        self.app, self._data, self._where = app, None, ""

    def _load(self) -> dict:
        if self._data is None:
            given = os.environ.get("ROSTRUM_NOTICES")
            if given:
                self._data = json.loads(Path(given).read_text(encoding="utf-8"))     # fails loudly when missing
                self._where = f"Full licence texts: {Path(given).with_name('NOTICES.txt')}"
            else:
                self._data = generate(self.app)
                self._where = "Development checkout: the installer ships the full licence texts as NOTICES.txt beside the app."
        return self._data

    @Property(str, constant=True)
    def appName(self) -> str:
        return NAMES.get(self.app, "Rostrum")

    @Property(str, constant=True)
    def version(self) -> str:
        return VERSION

    @Property("QVariantList", constant=True)
    def items(self) -> list:
        return self._load()["items"]

    @Property(str, constant=True)
    def where(self) -> str:
        self._load()
        return self._where
