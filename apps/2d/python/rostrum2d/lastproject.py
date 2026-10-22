"""The person's last Rostrum2D project, read the way the 2D screen's Open recent list reads it (settings "recent":
rows {folder, item}, newest first, only ones still on disk). The MCP server opens the first row when it is started
with no options, so an agent works on what the person was just working on.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rostrum_core import project
from rostrum_core.storage import paths

from . import KIND, settings

DEFAULT_ITEM = "main"


def doc_file(folder, item) -> Path:
    return paths(folder, item, KIND.ext)["doc"]


def recent_rows() -> list[dict]:
    """[{folder, item}] newest first, the ones whose document is still on disk."""
    return [{"folder": r["folder"], "item": r["item"]} for r in settings.read_settings().get("recent", [])
            if doc_file(r["folder"], r["item"]).is_file()]


def describe(row: dict) -> dict:
    """{folder, item, name, changed}: what a person sees in Open recent, plus when the file last changed (ISO, local time)."""
    f = doc_file(row["folder"], row["item"])
    name = Path(row["folder"]).name
    return {"folder": row["folder"], "item": row["item"], "name": name if row["item"] == DEFAULT_ITEM else f"{name} ({row['item']})",
            "changed": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")}


def last_project() -> dict | None:
    """The newest recent row, or None when the person has no recent project."""
    rows = recent_rows()
    return rows[0] if rows else None


def docs_in(folder) -> list[str]:
    """The 2D documents in a project folder, newest change first."""
    ids = [it["id"] for it in project.items(folder, KIND.name)] if Path(folder).is_dir() else []
    return sorted((i for i in ids if doc_file(folder, i).is_file()), key=lambda i: doc_file(folder, i).stat().st_mtime, reverse=True)


def default_item(folder, explicit: bool) -> str | None:
    """Which document to open in `folder` when none is named: the one its recent row names, else the only / newest one in
    docs, else (only when the folder was asked for explicitly) "main", to be created. None = nothing to open."""
    here = str(Path(folder).resolve())
    for row in recent_rows():
        if str(Path(row["folder"]).resolve()) == here:
            return row["item"]
    found = docs_in(folder)
    return found[0] if found else (DEFAULT_ITEM if explicit else None)
