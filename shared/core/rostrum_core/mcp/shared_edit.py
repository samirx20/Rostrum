"""The shared tools that change a document or a job: edit_document, run_script, run_stop, inspect_job.

The document changes only through `ctx.apply` / `ctx.run_script` (= `Document.apply` / `Document.run_script`).
"""
from __future__ import annotations

import json

from ..errors import RostrumError, codes
from .jobs import MAX_WAIT_S, outcome
from .reply import Reply
from .tools import Tools

_ITEM = {"item": {"type": "string", "description": "The document's project item id. Optional when only one document is open."}}
_GROUP = {"group": {"type": "string", "description": "Changes with the same group are reviewed and undone together. Default: one per agent turn."}}
_CALL = {"type": "object", "required": ["op"], "additionalProperties": False, "properties": {
    "op": {"type": "string", "description": "Operation name, from inspect_operations."},
    "target": {"type": "array", "items": {"type": "string"}, "description": "Ids the operation acts on."},
    "args": {"type": "object", "description": "The operation's arguments."}}}


def _problems(doc) -> set[str]:
    check = getattr(getattr(doc, "kind", None), "check", None)
    return {json.dumps(p, sort_keys=True, default=str) for p in check(doc.data)} if check else set()


def register(tools: Tools):
    @tools.tool("edit_document", {"required": ["ops"], "properties": {
        **_ITEM, "ops": {"type": "array", "minItems": 1, "items": _CALL}, "label": {"type": "string"}, **_GROUP}})
    def edit_document(ctx, args):
        """Apply a list of operations, all or nothing, as one change in the history."""
        doc = ctx.document(args.get("item"))
        before = _problems(doc)
        group = ctx.group if "group" not in args else args["group"]
        change = ctx.apply(doc, args["ops"], args.get("label"), group)
        names = [c["op"] for c in args["ops"]]
        if change is None:
            return Reply(f"Nothing changed: {', '.join(names)} left every value as it was; no history step recorded.", {"seq": doc.seq})
        new = [json.loads(p) for p in sorted(_problems(doc) - before)]
        changed = {"seq": change.seq, "ops": names, "group": group, "new_check_failures": new}
        warn = [f"This change broke a check: {p}" for p in new] + doc.kind.registry.alias_notes(args["ops"])
        return Reply(f"Applied {len(names)} operation{'s' * (len(names) != 1)} ({', '.join(names)}) as change {change.seq}, group {group}.",
                     {"seq": change.seq}, warnings=warn, changed=changed)

    @tools.tool("run_script", {"required": ["source"], "properties": {
        **_ITEM, "source": {"type": "string", "description": "Python source for this app's script layer."},
        "name": {"type": "string", "default": "agent_script.py", "description": "The script's name; a script run again under the same name merges."},
        "force": {"anyOf": [{"type": "boolean"}, {"type": "array", "items": {"type": "string"}}],
                  "description": "Overwrite what a person changed: true for all held-back values, or a list of their keys."},
        "detail": {"type": "boolean", "default": False, "description": "List every removed item in the reply's data (else counts and the first few)."}}})
    def run_script(ctx, args):
        """Run a Python script that builds the document tree and merge it in. What a person moved by hand stays; held-back values are listed."""
        if ctx.app.run_source is None:
            raise RostrumError(codes.BAD_ARGUMENT, "", "this app", "has no script layer wired to the server")
        doc, name = ctx.document(args.get("item")), args.get("name", "agent_script.py")
        run = ctx.app.run_source
        tree = run(args["source"], name, doc) if getattr(run, "wants_doc", False) else run(args["source"], name)
        report = ctx.run_script(doc, name, tree, args.get("force", False))
        held = [dict(h) for h in report.held]
        changed = {"seq": report.change.seq, "ops": [c["op"] for c in report.change.calls], "group": report.change.session} if report.change else None
        return Reply(report.summary(), {"held": held, "removed": report.removed if args.get("detail") else {"count": len(report.removed), "first": report.removed[:5]}, "seq": doc.seq}, warnings=report.warnings(), changed=changed)

    @tools.tool("inspect_job", {"properties": {
        "job_id": {"type": "string", "description": "The job. Without it: every job in the queue's order (running, waiting, then ended)."},
        "wait_s": {"type": "number", "minimum": 0, "maximum": MAX_WAIT_S, "default": 0}}})
    def inspect_job(ctx, args):
        """A job's status and progress, and its result when done. wait_s (up to 25) waits for it to finish. Without job_id:
        the jobs queue in order (one heavy job runs at a time; the rest wait their turn)."""
        if "job_id" not in args:
            jobs = [j.state() for j in ctx.jobs.listing()] if hasattr(ctx.jobs, "listing") else []
            return Reply(f"{len(jobs)} job{'s' * (len(jobs) != 1)}: " + ("; ".join(f"{j['job_id']} {j['label']} {j['status']}" for j in jobs) or "none"),
                         {"jobs": jobs})
        return outcome(ctx.jobs.wait(args["job_id"], args.get("wait_s", 0)), ctx.tool)

    @tools.tool("run_stop", {"required": ["job_id"], "properties": {"job_id": {"type": "string"}}})
    def run_stop(ctx, args):
        """Stop a job by its id. Its output is marked incomplete."""
        job = ctx.jobs.cancel(args["job_id"])
        return Reply(f"Stop requested for {job.id} ({job.label}); it is {job.status}.", job.state())
