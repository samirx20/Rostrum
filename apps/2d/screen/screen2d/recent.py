"""Open recent: the last projects opened, newest first, kept in the user settings file (rostrum2d.settings)."""
from __future__ import annotations

from pathlib import Path

from rostrum2d import KIND, settings
from rostrum_core import userhome
from rostrum_core.storage import paths

KEEP = 8


def rows() -> list[dict]:
    """[{folder, item, path, label}] of the ones still on disk (missing ones are dropped from the list shown)."""
    out = []
    for r in settings.read_settings().get("recent", []):
        doc = paths(r["folder"], r["item"], KIND.ext)["doc"]
        if doc.is_file():
            name = Path(r["folder"]).name
            out.append({**r, "path": str(doc), "label": name if r["item"] == "main" else f"{name} ({r['item']})"})
    return out[:KEEP]


def add(folder, item) -> None:
    """Put this project first (once); keeps KEEP."""
    row = {"folder": str(Path(folder).resolve()), "item": item}
    with userhome.locked(settings.settings_path()):          # two windows at once never lose or crash each other
        data = settings.read_settings()
        data["recent"] = ([row] + [r for r in data.get("recent", []) if r != row])[:KEEP]
        settings.write_settings(data)
