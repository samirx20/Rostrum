"""Which project the Sound server works on: the person's last song at start-up, and switching while it runs.

    inspect_recent_projects {}                         the person's recent songs (folder, item, name, last changed)
    run_open_project {folder, item?}                   close the open songs and open another project, as start-up does

Start-up (server.py) and run_open_project both go through `app.open_project`: the one engine process stays, the shared
markers and the renders folder follow the new project, and every other tool works on it at once. Switching changes no
document and does not touch the person's Recent songs list.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import lastproject as last
from .. import script_scope
from .app import NO_PROJECT, open_project


def start_choice(folder: str | None, items: list[str] | None) -> tuple[str | None, list[str]]:
    """What to open at start-up: --project / --item as given, else the person's last song (nothing when they have none)."""
    if folder:
        return folder, items or [last.default_item(folder, explicit=True)]
    row = last.last_project()
    return (row["folder"], items or [row["item"]]) if row else (None, [])


def with_no_project_sentence(runtime) -> None:
    """With no project open, inspect_project says so in one plain sentence (the shared reply talks about a missing option)."""
    old = runtime.tools.get("inspect_project")

    def inspect_project(ctx, args):
        if ctx.app.folder or ctx.app.documents:
            return old.fn(ctx, args)
        return Reply(NO_PROJECT, {"app": ctx.app.name, "open": [], "items": None, "recent": last.recent_rows()})
    runtime.tools._tools["inspect_project"] = dataclasses.replace(old, fn=inspect_project)


EDIT_DOCUMENT = (
    "Apply a list of operations, all or nothing, as one change in the history. Read inspect_guide 'start-here' and "
    "'writing-parts' first; list the operations with inspect_operations (name=... for one's arguments). Targets are item ids "
    "(the song itself is \"root\"). A bare number for a time or a length is SECONDS: beats are {\"beat\": 8} for a time "
    "(\"at\") and {\"beats\": 2} for a length (\"dur\", \"length\"). A volume is gain 0 … 4 as a bare number, or in dB as "
    "{\"db\": -6}. Several parts at once: run_script is shorter.")
ERROR_HINT = "Check inspect_operations (name=<op>) for the arguments, and inspect_guide 'start-here' for how replies work."


def with_sound_edit_help(runtime) -> None:
    """edit_document is shared; Sound says what an agent can't guess (units, ids, where to read) and gives every
    failure a hint (a more exact one stays)."""
    old = runtime.tools.get("edit_document")

    def edit_document(ctx, args):
        try:
            return old.fn(ctx, args)
        except RostrumError as e:
            e.hint = e.hint or ERROR_HINT
            raise
    runtime.tools._tools["edit_document"] = dataclasses.replace(old, fn=edit_document, description=EDIT_DOCUMENT)


def with_script_print(runtime) -> None:
    """run_script's reply carries what the script printed (as warnings), so a script can show what it computed."""
    old = runtime.tools.get("run_script")

    def run_script(ctx, args):
        script_scope.forget_printed()
        try:
            return old.fn(ctx, args)
        finally:
            for line in script_scope.printed():
                ctx.note(f"print: {line}")
    runtime.tools._tools["run_script"] = dataclasses.replace(old, fn=run_script)


def register(tools: Tools):
    @tools.tool("inspect_recent_projects", {})
    def inspect_recent_projects(ctx, args):
        """The person's recent RostrumSound songs, newest first: folder, item, name and when the file last changed. Pick one for run_open_project; the first is what the server opens at start-up."""
        rows = [last.describe(r) for r in last.recent_rows()]
        now = ctx.app.folder
        listed = "; ".join(f'{r["name"]} ({r["folder"]}, item {r["item"]}, changed {r["changed"]})' for r in rows)
        open_now = f" Open now: {now}." if now else " No project is open."
        return Reply((f"{len(rows)} recent project(s): {listed}." if rows else "The person has no recent RostrumSound songs.") + open_now,
                     {"recent": rows, "open": now})

    @tools.tool("run_open_project", {"required": ["folder"], "properties": {
        "folder": {"type": "string", "description": "The project folder (absolute path; one from inspect_recent_projects, or any folder with docs/<item>.trk)."},
        "item": {"type": "string", "description": "The song to open. Default: the one its recent row names, else the only / newest in the folder."}}})
    def run_open_project(ctx, args):
        """Switch to another project: closes the open songs and opens this folder's (every change is saved at once, so nothing is lost); the engine keeps running, and all other tools work on the new project. Use inspect_recent_projects to see what the person has."""
        folder = Path(args["folder"])
        if not folder.is_dir():
            raise RostrumError(codes.NOT_FOUND, "run_open_project", f'"{folder}"', "is not a project folder",
                               list(dict.fromkeys(r["folder"] for r in last.recent_rows())), "Pass a folder from inspect_recent_projects.")
        found = last.docs_in(folder)
        item = args.get("item") or last.default_item(folder, explicit=True)
        if item not in found and found:
            raise RostrumError.not_found("run_open_project", "song", item, found, f"the songs in {folder}")
        if item not in found:
            ctx.note(f'{folder} had no song yet: "{item}" was created there.')
        open_project(ctx.app, folder, [item])
        return Reply(f'Opened {ctx.app.folder} (song "{item}"). Other tools now work on it.',
                     {"folder": ctx.app.folder, "item": item, "documents": sorted(ctx.app.documents)})
