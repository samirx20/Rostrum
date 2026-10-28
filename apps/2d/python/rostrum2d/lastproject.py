"""The person's recent Rostrum2D projects, read from the one Open recent list the 2D screen keeps too
(rostrum_core/recent.py: rows {folder, item, name}, newest first, only ones still on disk). The MCP server lists them for
run_open_project (what "recent"); it never opens one by itself (rostrum_core/agent_start.py).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rostrum_core import project, recent
from rostrum_core.storage import paths

from . import KIND

DEFAULT_ITEM = "main"


def doc_file(folder, item) -> Path:
    return paths(folder, item, KIND.ext)["doc"]


def recent_rows() -> list[dict]:
    """[{folder, item}] newest first, the ones whose document is still on disk."""
    return [{"folder": r["folder"], "item": r["item"]} for r in recent.rows("2d", KIND.ext)]


def describe(row: dict) -> dict:
    """{folder, item, name, changed}: what a person sees in Open recent, plus when the file last changed (ISO, local time)."""
    f = doc_file(row["folder"], row["item"])
    name = Path(row["folder"]).name
    return {"folder": row["folder"], "item": row["item"], "name": name if row["item"] == DEFAULT_ITEM else f"{name} ({row['item']})",
            "changed": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")}


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
