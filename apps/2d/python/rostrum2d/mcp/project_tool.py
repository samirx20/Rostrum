"""Which project the 2D server works on: at start-up the agent's own (rostrum_core/agent_start.py: --project, else the
project this session last opened, else a fresh scratch project; never the person's by itself), and switching while it runs.

    run_open_project (what: recent) {}                         the person's recent projects (folder, item, name, last changed)
    run_open_project {folder, item?}                   close the open documents and open another project, as start-up does

Start-up (server.py) and run_open_project both go through `open_project`, so every other tool works on the new project
at once. Switching changes no document and does not touch the person's Open recent list.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Document, agent_start, bug, live
from rostrum_core.mcp import Reply, Tools, open_folder
from rostrum_core.storage import paths
from rostrum_paint import library

from rostrum2d import KIND
from .. import lastproject as last
from .. import sound_cues

tools = Tools()
NO_PROJECT = "No project is open. Open one in Rostrum2D, or call run_open_project with a folder."


def open_documents(project: str, items: list[str]) -> dict:
    """Open each item from the project folder (or start it empty when it has no file yet), saving after every change."""
    from ..ops_timing import use_project
    use_project(project)                     # layer.shift / layer.trim read this project's markers
    docs = {}
    for item in items:
        exists = paths(project, item, KIND.ext)["doc"].exists()
        doc = Document.open(project, item, KIND) if exists else Document.new(KIND, project, item)
        live.keep(doc)                       # one door for every save, shared with the person's window (rostrum_core.live)
        sound_cues.watch(doc, bug.note)   # cue markers follow their layers
        docs[item] = doc
    return docs


def start_choice(project: str | None, items: list[str] | None) -> agent_start.Start:
    """What to open at start-up: --project / --item as given, else this agent session's own project, else a fresh
    scratch project (agent_start.py); never the person's last project."""
    return agent_start.choose("rostrum-2d", KIND.ext, project, items, last.default_item)


def open_project(app, folder: str | None, items: list[str]) -> None:
    """Make `folder` / `items` the app's open documents (nothing open when there is no folder)."""
    app.documents = open_documents(folder, items) if folder else {}
    app.folder = str(folder) if folder else None
    library.use_project(app.folder)


def with_no_project_sentence(runtime) -> None:
    """With no project open, inspect_project says so in one plain sentence (the shared reply talks about a missing option)."""
    old = runtime.tools.get("inspect_project")

    def inspect_project(ctx, args):
        if ctx.app.folder or ctx.app.documents:
            return old.fn(ctx, args)
        return Reply(NO_PROJECT, {"app": ctx.app.name, "open": [], "items": None, "recent": last.recent_rows()})
    runtime.tools._tools["inspect_project"] = dataclasses.replace(old, fn=inspect_project)


@tools.tool("inspect_recent_projects", {})
def inspect_recent_projects(ctx, args):
    """The person's recent Rostrum2D projects, newest first: folder, item, name and when the file last changed. Pick one for run_open_project; the server never opens one by itself."""
    rows = [last.describe(r) for r in last.recent_rows()]
    now = ctx.app.folder
    listed = "; ".join(f'{r["name"]} ({r["folder"]}, item {r["item"]}, changed {r["changed"]})' for r in rows)
    open_now = f" Open now: {now}." if now else " No project is open."
    return Reply((f"{len(rows)} recent project(s): {listed}." if rows else "The person has no recent Rostrum2D projects.") + open_now,
                 {"recent": rows, "open": now})


@tools.tool("run_open_project", {"required": ["folder"], "properties": {
    "folder": {"type": "string", "description": open_folder.folder_description(KIND.ext)},
    "item": {"type": "string", "description": open_folder.item_description("document", last.DEFAULT_ITEM)}}})
def run_open_project(ctx, args):
    """Open a project, making it when it is new: closes the open documents (every change is already saved, so nothing is lost) and opens this folder's; then all other tools work on it. A folder that doesn't exist yet is made, and a document the folder doesn't have yet is started empty, e.g. {"folder": "C:/Users/me/Videos/launch"} or {"folder": "...", "item": "teaser"}. Use run_open_project (what: recent) to see what the person has."""
    return open_folder.open_folder(ctx, args, docs_in=last.docs_in, default_item=last.default_item, open_project=open_project)
