"""Which project the 3D server works on: at start-up the agent's own (rostrum_core/agent_start.py: --project, else the
project this session last opened, else a fresh scratch project with the start scene; never the person's by itself), and
switching while it runs, as 2D and Sound do.

    run_open_project (what: recent) {}           the person's recent scenes (the 3D window's Open recent), newest first
    run_open_project {folder, item?}             open another project's scene (or start one), every other tool follows

Switching changes no document and does not touch the person's Open recent list.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rostrum_core import agent_start, project, recent
from rostrum_core.mcp import Reply, Tools, open_folder
from rostrum_core.mcp.combine import combine
from rostrum_core.storage import paths

from rostrum3d import ops_mesh
from rostrum3d.kind import KIND

ITEM = "scene"                     # a new scene's item id (as the window's New: app/screen3d/files_3d.py)
tools = Tools()


def doc_file(folder, item) -> Path:
    return paths(folder, item, KIND.ext)["doc"]


def recent_rows() -> list[dict]:
    return [{"folder": r["folder"], "item": r["item"], "name": r["name"]} for r in recent.rows("3d", KIND.ext)]


def docs_in(folder) -> list[str]:
    """The 3D scenes in a project folder, newest change first."""
    ids = [it["id"] for it in project.items(folder, "3d")] if Path(folder).is_dir() else []
    return sorted((i for i in ids if doc_file(folder, i).is_file()), key=lambda i: doc_file(folder, i).stat().st_mtime, reverse=True)


def default_item(folder, explicit: bool) -> str | None:
    """The scene to open in `folder` when none is named: its recent row's, else the newest there, else (asked for
    explicitly) a new "scene"."""
    here = str(Path(folder).resolve())
    for row in recent_rows():
        if str(Path(row["folder"]).resolve()) == here:
            return row["item"]
    found = docs_in(folder)
    return found[0] if found else (ITEM if explicit else None)


def start_choice(folder: str | None, items: list[str] | None) -> agent_start.Start:
    """What to open at start-up (agent_start.py); never the person's last scene."""
    return agent_start.choose("rostrum-3d", KIND.ext, folder, items, default_item, word="scene")


def open_project(app, folder: str | None, items: list[str]) -> None:
    """Make `folder` / `items` the app's open scenes; the engine process stays, mesh reads follow the folder."""
    from .server import open_documents
    app.documents = open_documents(folder, items) if folder else {}
    app.folder = str(folder) if folder else None
    ops_mesh.use_engine(app.state.engine, app.folder)


@tools.tool("inspect_recent_projects", {})
def inspect_recent_projects(ctx, args):
    """The person's recent scenes, newest first; the server never opens one by itself."""
    rows = [{**r, "changed": datetime.fromtimestamp(doc_file(r["folder"], r["item"]).stat().st_mtime).isoformat(timespec="seconds")}
            for r in recent_rows()]
    listed = "; ".join(f'{r["name"]} ({r["folder"]}, item {r["item"]}, changed {r["changed"]})' for r in rows)
    now = f" Open now: {ctx.app.folder}." if ctx.app.folder else " No project is open."
    return Reply((f"{len(rows)} recent scene(s): {listed}." if rows else "The person has no recent Rostrum3D scenes.") + now,
                 {"recent": rows, "open": ctx.app.folder})


@tools.tool("run_open_project", {"required": ["folder"], "properties": {
    "folder": {"type": "string", "description": open_folder.folder_description(KIND.ext)},
    "item": {"type": "string", "description": open_folder.item_description("scene", ITEM)}}})
def run_open_project(ctx, args):
    """Open a folder's scene (a new folder or scene is made, as New does); nothing open is lost."""
    return open_folder.open_folder(ctx, args, docs_in=docs_in, default_item=default_item, open_project=open_project, word="scene")


combine(tools, "run_open_project", "The person's scenes: open one (default), or list the recent ones.",
        {"open": "run_open_project", "recent": "inspect_recent_projects"}, default="open")
