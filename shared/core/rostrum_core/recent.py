"""Open recent, for every app: the one place the list lives and is read (the window's ≡ menu and start screen, the MCP
servers' "the person's last project"). `<userhome>/settings/<app>-recent.json`: rows {folder, item, name}, newest
first. A scripted run's home is its scratch one (userhome), so tests and checks never touch the person's list.

    rows(app, ext)                      the rows whose document is still on disk, + `changed` (the file's mtime)
    remember(app, ext, folder, item, name)
"""
from __future__ import annotations

import json
from pathlib import Path

from . import userhome
from .storage import paths, write_atomic

KEEP = 10


def file(app: str) -> Path:
    return userhome.home() / "settings" / f"{app}-recent.json"


def rows(app: str, ext: str) -> list[dict]:
    try:
        data = json.loads(file(app).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for r in data:
        doc = paths(r["folder"], r["item"], ext)["doc"]
        if doc.is_file():
            out.append({"folder": r["folder"], "item": r["item"], "name": r.get("name") or Path(r["folder"]).name,
                        "changed": doc.stat().st_mtime})
    return out


def remember(app: str, ext: str, folder, item: str, name: str) -> None:
    """Put this project first (once); keeps KEEP. Two windows at once never lose each other's row."""
    row = {"folder": str(Path(folder).resolve()), "item": item, "name": name}
    with userhome.locked(file(app)):
        old = [{k: r[k] for k in ("folder", "item", "name")} for r in rows(app, ext)
               if (r["folder"], r["item"]) != (row["folder"], item)]
        write_atomic(file(app), json.dumps(([row] + old)[:KEEP], indent=1, ensure_ascii=False))
