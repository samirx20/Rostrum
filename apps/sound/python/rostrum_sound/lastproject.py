"""The person's recent RostrumSound songs, read the way the Sound screen's Recent songs list reads it
(rostrum_core/recent.py, the one Open recent list: rows {folder, item, name}, newest first; gone songs left out).
The MCP server lists them for run_open_project (what "recent"); it never opens one by itself (rostrum_core/agent_start.py).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rostrum_core import project, recent
from rostrum_core.storage import paths

from . import KIND

DEFAULT_ITEM = "song"             # a new song's item id inside its project folder (screensound/files_sound.py ITEM)


def doc_file(folder, item) -> Path:
    return paths(folder, item, KIND.ext)["doc"]


def recent_rows() -> list[dict]:
    """[{folder, item, name}] newest first; songs that are gone are left out."""
    return [{k: r[k] for k in ("folder", "item", "name")} for r in recent.rows("sound", KIND.ext)]


def describe(row: dict) -> dict:
    """{folder, item, name, changed}: the name the Recent list shows, and when the file last changed (ISO, local time)."""
    f = doc_file(row["folder"], row["item"])
    return {"folder": row["folder"], "item": row["item"], "name": row.get("name") or Path(row["folder"]).name,
            "changed": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")}


def docs_in(folder) -> list[str]:
    """The Sound documents in a project folder, newest change first."""
    ids = [it["id"] for it in project.items(folder, "sound")] if Path(folder).is_dir() else []
    return sorted((i for i in ids if doc_file(folder, i).is_file()), key=lambda i: doc_file(folder, i).stat().st_mtime, reverse=True)


def default_item(folder, explicit: bool) -> str | None:
    """Which song to open in `folder` when none is named: the one its recent row names, else the only / newest one in
    docs, else (only when the folder was asked for explicitly) "song", to be created. None = nothing to open."""
    here = str(Path(folder).resolve())
    for row in recent_rows():
        if str(Path(row["folder"]).resolve()) == here:
            return row["item"]
    found = docs_in(folder)
    return found[0] if found else (DEFAULT_ITEM if explicit else None)
