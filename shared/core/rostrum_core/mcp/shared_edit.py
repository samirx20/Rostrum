"""The shared tools that change a document or a job: edit_document, run_script, run_stop, inspect_job.

The document changes only through `ctx.apply` / `ctx.run_script` (= `Document.apply` / `Document.run_script`).
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from ..errors import RostrumError, codes
from .edit_summary import sentence, summarize
from .faults import NOTES
from .jobs import MAX_WAIT_S, outcome
from .reply import Reply
from .tools import Tools

_ITEM = {"item": {"type": "string", "description": "Project item id; default the open document."}}
_GROUP = {"group": {"type": "string", "description": "Changes with the same group are reviewed and undone together. Default: one per agent turn."}}
_CALL = {"type": "object", "required": ["op"], "additionalProperties": False, "properties": {
    "op": {"type": "string", "description": "Operation name, from inspect_operations."},
    "target": {"type": "array", "items": {"type": "string"}, "description": "Ids the operation acts on."},
    "args": {"type": "object", "description": "The operation's arguments."}}}


def _problems(doc) -> set[str]:
    check = getattr(getattr(doc, "kind", None), "check", None)
    return {json.dumps(p, sort_keys=True, default=str) for p in check(doc.data)} if check else set()


def _new_advice(doc, before: set) -> list[str]:
    """The app's advice a call made new (a valid state that is probably not what was meant), as reply warnings."""
    return [a for a in doc.kind.advice(doc.data) if a not in before]


def _script_source(args) -> tuple[str, Path | None]:
    """run_script's text: `source`, or the file at `path` (exactly one of them). Returns (text, file or None)."""
    if ("source" in args) == ("path" in args):
        raise RostrumError(codes.BAD_ARGUMENT, "run_script", "the script", "needs exactly one of `source` or `path`",
                           ["source", "path"], 'e.g. {"path": "C:/work/promo.py"}, or {"source": "comp(\\"main\\", ...)", "name": "promo.py"}')
    if "source" in args:
        return args["source"], None
    file = Path(args["path"])
    if not file.is_absolute() or not file.is_file():
        raise RostrumError(codes.NOT_FOUND, "run_script", f'"{file}"', "is not a script file", ["an absolute path to a .py file"],
                           "Write the script to a file first, or pass its text as `source`.")
    return file.read_text(encoding="utf-8"), file


def register(tools: Tools):
    @tools.tool("edit_document", {"required": ["ops"], "properties": {
        **_ITEM, "ops": {"type": "array", "minItems": 1, "items": _CALL}, "label": {"type": "string"}, **_GROUP}})
    def edit_document(ctx, args):
        """Apply a list of operations, all or nothing, as one change in the history."""
        doc = ctx.document(args.get("item"))
        before, advised = _problems(doc), set(doc.kind.advice(doc.data))
        group = ctx.group if "group" not in args else args["group"]
        change = ctx.apply(doc, args["ops"], args.get("label"), group)
        names = [c["op"] for c in args["ops"]]
        if change is None:
            return Reply(f"Nothing changed: {', '.join(names)} left every value as it was; no history step recorded.", {"seq": doc.seq})
        new = [json.loads(p) for p in sorted(_problems(doc) - before)]
        items = summarize(doc, change)
        changed = {"seq": change.seq, "ops": names, "group": group, "new_check_failures": new, "items": items}
        warn = [f"This change broke a check: {p}" for p in new] + doc.kind.registry.alias_notes(args["ops"]) + _new_advice(doc, advised)
        return Reply(f"Applied {len(names)} operation{'s' * (len(names) != 1)} ({', '.join(names)}) as change {change.seq}, group {group}. {sentence(items)}".rstrip(),
                     {"seq": change.seq}, warnings=warn, changed=changed)

    @tools.tool("run_script", {"properties": {
        **_ITEM, "source": {"type": "string", "description": "The script as text (Python). Give `source` or `path`."},
        "path": {"type": "string", "description": "A .py file to run instead of `source` (absolute path)."},
        "name": {"type": "string", "default": "agent_script.py", "description": "Same name = replaces what that script made (a person's edits stay); a new name adds a second copy. Default: the file name."},
        "force": {"anyOf": [{"type": "boolean"}, {"type": "array", "items": {"type": "string"}}],
                  "description": "Overwrite values someone else changed since this script's last run: true for all, or the keys the reply named."},
        "detail": {"type": "boolean", "default": False, "description": "List every removed item in the reply's data (else counts and the first few)."}}})
    def run_script(ctx, args):
        """Run a Python script that builds the document tree and merge it in: {"path": "C:/work/promo.py"} runs a file, {"source": "...", "name": "promo.py"} runs text.
        What a person moved by hand stays; held-back values are listed. Run again under the same `name` it replaces what it made (the file name, with `path`); under a new name it adds a second copy."""
        if ctx.app.run_source is None:
            raise RostrumError(codes.BAD_ARGUMENT, "", "this app", "has no script layer wired to the server")
        source, file = _script_source(args)
        doc, name = ctx.document(args.get("item")), args.get("name") or (file.name if file else "agent_script.py")
        run = ctx.app.run_source
        tree = run(source, name, doc) if getattr(run, "wants_doc", False) else run(source, name)
        advised = set(doc.kind.advice(doc.data))
        report = ctx.run_script(doc, name, tree, args.get("force", False))
        held = [dict(h) for h in report.held]
        changed = {"seq": report.change.seq, "ops": [c["op"] for c in report.change.calls], "group": report.change.session} if report.change else None
        reply = Reply(report.summary(), {"held": held, "removed": report.removed if args.get("detail") else {"count": len(report.removed), "first": report.removed[:5]}, "seq": doc.seq}, warnings=[*getattr(tree, "notes", ()), *report.warnings(), *_new_advice(doc, advised)], changed=changed)
        look = args.get("look")
        return ctx.app.script_look(ctx, doc, look, reply) if look not in (None, False, []) and ctx.app.script_look else reply

    @tools.tool("inspect_job", {"properties": {
        "job_id": {"type": "string", "description": "The job; without it, the whole queue in order."},
        "wait_s": {"type": "number", "minimum": 0, "maximum": MAX_WAIT_S, "default": 0}}})
    def inspect_job(ctx, args):
        """A job's status, progress and result when done (other programs' jobs too, read-only); wait_s (up to 25) waits for it.
        Without job_id: the queue in order (one heavy job runs at a time)."""
        if "job_id" not in args:
            jobs = [j.state() for j in ctx.jobs.listing()] if hasattr(ctx.jobs, "listing") else []
            return Reply(f"{len(jobs)} job{'s' * (len(jobs) != 1)}: " + ("; ".join(f"{j['job_id']} {j['label']} {j['status']}" for j in jobs) or "none"),
                         {"jobs": jobs})
        return outcome(ctx.jobs.wait(args["job_id"], args.get("wait_s", 0)), ctx.tool)

    @tools.tool("run_stop", {"required": ["job_id"], "properties": {"job_id": {"type": "string"}}})
    def run_stop(ctx, args):
        """Stop a job by its id (this server's or another program's); its output is marked incomplete."""
        job = ctx.jobs.cancel(args["job_id"])
        return Reply(f"Stop requested for {job.id} ({job.label}); it is {job.status}.{' ' + job.note if job.owner else ''}", job.state())


LOOK = {"look": {"anyOf": [{"type": "boolean"}, {"type": "array", "items": {"type": "number", "minimum": 0}, "minItems": 1, "maxItems": 12}],
                 "description": "Look in the same call: true (6 moments) or seconds, e.g. [2, 7, 12]: a contact sheet "
                                "to judge by eye. With notes: true the checks' measurements come too."}, **NOTES}
LOOK_LEAD = ("Write the whole film as one script; pass look to see stills of it, judge them yourself, edit and re-run under "
             "the same name. ")


def with_look(tools: Tools):
    """run_script gains `look` (the app gave App.script_look): its schema and the lead of its description."""
    t = tools.get("run_script")
    tools._tools["run_script"] = dataclasses.replace(t, description=LOOK_LEAD + t.description,
                                                     schema={**t.schema, "properties": {**t.schema["properties"], **LOOK}})

