"""Which project the 2D server works on: the person's last one at start-up, and switching while it runs.

    inspect_recent_projects {}                         the person's recent projects (folder, item, name, last changed)
    run_open_project {folder, item?}                   close the open documents and open another project, as start-up does

Start-up (server.py) and run_open_project both go through `open_project`, so every other tool works on the new project
at once. Switching changes no document and does not touch the person's Open recent list.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from rostrum_core import Document, live
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.storage import paths

from rostrum2d import KIND
from .. import lastproject as last

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
        docs[item] = doc
    return docs


def start_choice(project: str | None, items: list[str] | None) -> tuple[str | None, list[str]]:
    """What to open at start-up: --project / --item as given, else the person's last project (nothing when they have none)."""
    if project:
        return project, items or [last.default_item(project, explicit=True)]
    row = last.last_project()
    return (row["folder"], items or [row["item"]]) if row else (None, [])


def open_project(app, folder: str | None, items: list[str]) -> None:
    """Make `folder` / `items` the app's open documents (nothing open when there is no folder)."""
    app.documents = open_documents(folder, items) if folder else {}
    app.folder = str(folder) if folder else None


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
    """The person's recent Rostrum2D projects, newest first: folder, item, name and when the file last changed. Pick one for run_open_project; the first is what the server opens at start-up."""
    rows = [last.describe(r) for r in last.recent_rows()]
    now = ctx.app.folder
    listed = "; ".join(f'{r["name"]} ({r["folder"]}, item {r["item"]}, changed {r["changed"]})' for r in rows)
    open_now = f" Open now: {now}." if now else " No project is open."
    return Reply((f"{len(rows)} recent project(s): {listed}." if rows else "The person has no recent Rostrum2D projects.") + open_now,
                 {"recent": rows, "open": now})


@tools.tool("run_open_project", {"required": ["folder"], "properties": {
    "folder": {"type": "string", "description": "The project folder (absolute path; one from inspect_recent_projects, or any folder with docs/<item>.mtn)."},
    "item": {"type": "string", "description": "The document to open. Default: the one its recent row names, else the only / newest in the folder."}}})
def run_open_project(ctx, args):
    """Switch to another project: closes the open documents and opens this folder's (every change is saved at once, so nothing is lost); then all other tools work on it. Use inspect_recent_projects to see what the person has."""
    folder = Path(args["folder"])
    if not folder.is_dir():
        raise RostrumError(codes.NOT_FOUND, "run_open_project", f'"{folder}"', "is not a project folder",
                           list(dict.fromkeys(r["folder"] for r in last.recent_rows())), "Pass a folder from inspect_recent_projects.")
    found = last.docs_in(folder)
    item = args.get("item") or last.default_item(folder, explicit=True)
    if item not in found and found:
        raise RostrumError.not_found("run_open_project", "document", item, found, f"the documents in {folder}")
    if item not in found:
        ctx.note(f'{folder} had no document yet: "{item}" was created there.')
    open_project(ctx.app, str(folder.resolve()), [item])
    return Reply(f'Opened {ctx.app.folder} (document "{item}"). Other tools now work on it.',
                 {"folder": ctx.app.folder, "item": item, "documents": sorted(ctx.app.documents)})
