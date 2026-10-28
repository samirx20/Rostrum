"""Which project the Sound server works on: at start-up the agent's own (rostrum_core/agent_start.py: --project, else the
project this session last opened, else a fresh scratch project; never the person's by itself), and switching while it runs.

    run_open_project (what: recent) {}                         the person's recent songs (folder, item, name, last changed)
    run_open_project {folder, item?}                   close the open songs and open another project, as start-up does

Start-up (server.py) and run_open_project both go through `app.open_project`: the one engine process stays, the shared
markers and the renders folder follow the new project, and every other tool works on it at once. Switching changes no
document and does not touch the person's Recent songs list.
"""
from __future__ import annotations

import copy
import dataclasses
from pathlib import Path

from rostrum_core import RostrumError, agent_start, codes
from rostrum_core.mcp import Reply, Tools, open_folder

from .. import KIND
from .. import lastproject as last
from .. import note_ranges, script_scope
from ..diagnose import FIXES
from . import edit_examples, range_target, script_shared, script_twins
from .app import NO_PROJECT, open_project


def start_choice(folder: str | None, items: list[str] | None) -> agent_start.Start:
    """What to open at start-up: --project / --item as given, else this agent session's own song, else a fresh scratch
    project (agent_start.py); never the person's last song."""
    return agent_start.choose("rostrum-sound", KIND.ext, folder, items, last.default_item, word="song")


def with_no_project_sentence(runtime) -> None:
    """With no project open, inspect_project says so in one plain sentence (the shared reply talks about a missing option)."""
    old = runtime.tools.get("inspect_project")

    def inspect_project(ctx, args):
        if ctx.app.folder or ctx.app.documents:
            return old.fn(ctx, args)
        return Reply(NO_PROJECT, {"app": ctx.app.name, "open": [], "items": None, "recent": last.recent_rows()})
    runtime.tools._tools["inspect_project"] = dataclasses.replace(old, fn=inspect_project)


def one_line(text: str, limit: int = 110) -> str:
    """A summary's first sentence, cut at a word when it is still long."""
    first = text.split(". ")[0].rstrip(".")
    return first if len(first) <= limit else first[:limit].rsplit(" ", 1)[0] + " …"


def with_short_operations(runtime) -> None:
    """inspect_operations answers a short list by default (name, target and one line each, about a fifth of the full text);
    `name` / `names` give the full arguments of one or several, `detail: "full"` of all."""
    old = runtime.tools.get("inspect_operations")

    def inspect_operations(ctx, args):
        args = dict(args)
        names = list(args.pop("names", None) or [])
        if names or "name" in args or args.get("detail") == "full":
            if names and "name" not in args:
                rows, said = [], []
                for n in names:
                    one = old.fn(ctx, {**args, "name": n})
                    rows += one.data["operations"]
                    said.append(one.summary)
                return Reply(" ".join(said), {"operations": rows})
            return old.fn(ctx, args)
        full = old.fn(ctx, args)
        rows = [{**r, "summary": one_line(r["summary"])} for r in full.data["operations"]]
        return Reply(f"{len(rows)} operations (one line each; `name` or `names` for the full arguments of one or several, detail \"full\" for all).", {"operations": rows})
    schema = copy.deepcopy(old.schema)
    schema.setdefault("properties", {})["names"] = {"type": "array", "items": {"type": "string"}, "description": "Several operations at once, each with its full argument schema."}
    runtime.tools._tools["inspect_operations"] = dataclasses.replace(
        old, fn=inspect_operations, schema=schema,
        description=old.description + " A short list by default (one line each); `name` / `names` give the full arguments of one or several operations; detail \"full\" gives everything.")


def with_job_word(runtime) -> None:
    """inspect_job and run_stop also take `job` (a render's reply calls the id "job": agents passed it back as written and were
    refused); `job_id` stays the argument."""
    for name in ("inspect_job", "run_stop"):
        old = runtime.tools.get(name)

        def fn(ctx, args, old=old, name=name):
            args = dict(args)
            if "job" in args:
                args.setdefault("job_id", args.pop("job"))
            if name == "run_stop" and "job_id" not in args:
                raise RostrumError(codes.BAD_ARGUMENT, "run_stop", "job_id", "is needed", ["job_id"], "The id a render's reply names (job_id, or job).")
            return old.fn(ctx, args)
        schema = copy.deepcopy(old.schema)
        schema["properties"]["job"] = {"type": "string", "description": "The same as job_id."}
        schema["required"] = [r for r in schema.get("required", []) if r != "job_id"]
        runtime.tools._tools[name] = dataclasses.replace(old, fn=fn, schema=schema)


EDIT_DOCUMENT = (
    "Apply operations as one change, all or nothing: one-off touch-ups (parts belong in run_script). `ops`: a list of "
    "{op, target?, args?} (inspect_operations). A target is an id (\"drums\"; the song \"root\") or notes "
    "{\"track\": \"keys\", \"from\": {\"bar\": 1}, \"to\": {\"bar\": 9}}. A bare number is SECONDS: beats are {\"beat\": 8}, "
    "a length {\"beats\": 2}. Example: " + edit_examples.LINES[-1][1] + " Calls: guide 'agent-reference'.")
RUN_SCRIPT = ("Time in bars: bar(n) is where bar n starts; length(bar(9)) is 8 bars. Example source: \"tempo(96); length(bar(9))\\n"
              "t = track('keys', builtIn='piano')\\nt.note('D4', at=bar(1), dur=beats(4))\". Names: inspect_guide 'script'.")
ERROR_HINT = "Check inspect_operations (name=<op>) for the arguments, and inspect_guide 'agent-reference' for how replies work."


def with_sound_edit_help(runtime) -> None:
    """edit_document is shared; Sound says what an agent can't guess (units, ids, where to read) and gives every
    failure a hint (a more exact one stays)."""
    old = runtime.tools.get("edit_document")

    def edit_document(ctx, args):
        try:
            doc = ctx.document(args.get("item"))
            return old.fn(ctx, {**args, "ops": range_target.expand(doc, doc.kind.registry, args["ops"])})
        except RostrumError as e:
            e.hint = e.hint or ERROR_HINT
            raise
    schema = copy.deepcopy(old.schema)
    schema["properties"]["ops"]["items"]["properties"]["target"]["items"] = range_target.SCHEMA_ITEM
    runtime.tools._tools["edit_document"] = dataclasses.replace(old, fn=edit_document, description=EDIT_DOCUMENT, schema=schema)


def with_script_print(runtime) -> None:
    """run_script's reply carries what the script printed (as warnings), so a script can show what it computed, and
    notes a track's sound can't play (note_ranges: said now, not first by the render)."""
    old = runtime.tools.get("run_script")

    def run_script(ctx, args):
        script_twins.refuse_second_copy(ctx.document(args.get("item")), args)
        script_shared.publish(ctx, ctx.document(args.get("item")), args)      # marker(..., shared=True), before the merge
        script_scope.forget_printed()         # after the check: its dry run printed too
        try:
            out = old.fn(ctx, args)
            if args.get("path") and not args.get("name"):        # the name came from the file: say so, a new file adds a copy
                ctx.note(f'script name: "{Path(args["path"]).name}" (from the file). A different file name adds a second copy beside '
                         'this run; to replace this run\'s notes from another file, give the same `name`.')
            for p in note_ranges.problems(ctx.document(args.get("item")).data, ctx.app.state.engine):
                ctx.note(f"{p['message']}. {FIXES['out-of-range']}.")
            return out
        finally:
            for line in script_scope.printed():
                ctx.note(f"print: {line}")
    runtime.tools._tools["run_script"] = dataclasses.replace(old, fn=run_script, description=f"{old.description} {RUN_SCRIPT}")


def register(tools: Tools):
    @tools.tool("inspect_recent_projects", {})
    def inspect_recent_projects(ctx, args):
        """The person's recent RostrumSound songs, newest first: folder, item, name and when the file last changed. Pick one for run_open_project; the server never opens one by itself."""
        rows = [last.describe(r) for r in last.recent_rows()]
        now = ctx.app.folder
        listed = "; ".join(f'{r["name"]} ({r["folder"]}, item {r["item"]}, changed {r["changed"]})' for r in rows)
        open_now = f" Open now: {now}." if now else " No project is open."
        return Reply((f"{len(rows)} recent project(s): {listed}." if rows else "The person has no recent RostrumSound songs.") + open_now,
                     {"recent": rows, "open": now})

    @tools.tool("run_open_project", {"required": ["folder"], "properties": {
        "folder": {"type": "string", "description": open_folder.folder_description(KIND.ext)},
        "item": {"type": "string", "description": open_folder.item_description("song", last.DEFAULT_ITEM)}}})
    def run_open_project(ctx, args):
        """Open a project, making it when it is new: closes the open songs (every change is saved at once, so nothing is lost) and opens this folder's; the engine keeps running, and all other tools work on the new project. A folder that doesn't exist yet is made, and a song the folder doesn't have yet is started empty. Use run_open_project (what: recent) to see what the person has."""
        return open_folder.open_folder(ctx, args, docs_in=last.docs_in, default_item=last.default_item, open_project=open_project, word="song")
