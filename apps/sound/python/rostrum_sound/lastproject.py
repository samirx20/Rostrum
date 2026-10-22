"""The person's last RostrumSound song, read the way the Sound screen's Recent songs list reads it
(`<settings dir>/sound-recent.json`: rows {folder, item, name}, newest first; gone and untitled songs left out).
The MCP server opens the first row when it is started with no options, so an agent works on what the person was just doing.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rostrum_core import project
from rostrum_core.storage import paths

from . import KIND, settings

DEFAULT_ITEM = "song"             # a new song's item id inside its project folder (screensound.projects.ITEM)


def doc_file(folder, item) -> Path:
    return paths(folder, item, KIND.ext)["doc"]


def _untitled(folder) -> bool:
    try:
        Path(folder).resolve().relative_to((settings.settings_dir().parent / "untitled-songs").resolve())
        return True
    except ValueError:
        return False


def recent_rows() -> list[dict]:
    """[{folder, item, name}] newest first; songs that are gone (or untitled) are left out."""
    try:
        rows = json.loads((settings.settings_dir() / "sound-recent.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in rows if doc_file(r["folder"], r["item"]).is_file() and not _untitled(r["folder"])]


def describe(row: dict) -> dict:
    """{folder, item, name, changed}: the name the Recent list shows, and when the file last changed (ISO, local time)."""
    f = doc_file(row["folder"], row["item"])
    return {"folder": row["folder"], "item": row["item"], "name": row.get("name") or Path(row["folder"]).name,
            "changed": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")}


def last_project() -> dict | None:
    rows = recent_rows()
    return rows[0] if rows else None


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
