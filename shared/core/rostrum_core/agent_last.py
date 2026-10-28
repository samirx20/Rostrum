"""The project an agent last opened through an app's MCP server, per working folder, so a server started again for the same
agent session (a resumed session starts a fresh server) reopens that project instead of starting with none.

An agent's run_open_project never touches the person's Open recent list (recent.py); this is a separate, small record:
`<userhome>/settings/<app>-agent-last.json`, {working folder: {folder, item}}. A resumed session runs in the same working
folder, so the folder is the key.

    remember(app, folder, item)         run_open_project calls this (open_folder.py)
    pick(app, ext, person_row)          start-up: this folder's row when its document is newer than the person's last one
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import userhome
from .storage import paths, write_atomic

KEEP = 50


def file(app: str) -> Path:
    return userhome.home() / "settings" / f"{app}-agent-last.json"


def _here() -> str:
    return os.path.normcase(str(Path.cwd().resolve()))


def _read(app: str) -> dict:
    try:
        data = json.loads(file(app).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def remember(app: str, folder, item: str) -> None:
    """This working folder's agent now works on `folder` / `item` (newest last; keeps KEEP folders)."""
    try:
        with userhome.locked(file(app)):
            data = _read(app)
            data.pop(_here(), None)
            data[_here()] = {"folder": str(Path(folder).resolve()), "item": item}
            write_atomic(file(app), json.dumps(dict(list(data.items())[-KEEP:]), indent=1, ensure_ascii=False))
    except OSError:
        pass                                     # a record we could not write only loses the reopen convenience


def recall(app: str, ext: str) -> dict | None:
    """{folder, item} this working folder's agent last opened, when its document is still on disk."""
    row = _read(app).get(_here())
    if not row or not paths(row["folder"], row["item"], ext)["doc"].is_file():
        return None
    return {"folder": row["folder"], "item": row["item"]}


def pick(app: str, ext: str, person_row: dict | None) -> dict | None:
    """What a server started with no options opens: this folder's agent project when its document changed after the
    person's last one (a resumed session picks up where it stopped), else the person's last project."""
    mine = recall(app, ext)
    if mine is None or person_row is None:
        return mine or person_row

    def changed(r):
        return paths(r["folder"], r["item"], ext)["doc"].stat().st_mtime
    return mine if changed(mine) >= changed(person_row) else person_row
