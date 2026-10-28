"""run_script's `look` for Sound: write the whole piece, render it and read the listening check in one call.

Round 2's agents made many small calls, used about 2 of their 15 minutes and made whole-piece mistakes no single call
caught. The loop is one call: the script merges, then the shared hook (App.script_look, rostrum_core.mcp.shared_edit)
calls `after_run`, which runs render_mix itself (the one render path, with the arguments `look` gives), waits for the
job (up to WAIT_S) and answers with the script's line followed by render_mix's listening summary: loudness, the
weakest asked moments with their fixes, the files. A script that fails renders nothing (the hook runs only after a
merge); a `look` argument render_mix doesn't take is refused before the script runs (`with_look`).

2D's `look` takes seconds for stills; a sound is heard whole, so Sound's `look` is true or render_mix's arguments."""
from __future__ import annotations

import copy
import dataclasses

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply
from rostrum_core.mcp.jobs import outcome
from rostrum_core.mcp.shared_edit import LOOK_LEAD

from . import session_clock

WAIT_S = 150.0
AGAIN = "and run_script again with the edited source, the same name and look"
SCHEMA = {"anyOf": [{"type": "boolean"}, {"type": "object"}],
          "description": "Render and listen: true, or render_mix's arguments."}
LEAD = "The loop: one script for the whole piece, run with `look`; fix the script and run it again under the same name until DONE:. "


def _allowed(ctx) -> set:
    return set(ctx.tools.get("render_mix").schema.get("properties") or {}) - {"what"}     # the mix, not the MIDI file


def render_args(look, allowed, item=None) -> dict:
    """The render_mix arguments `look` asks for; a wrong one is refused (before the script runs: `with_look`)."""
    r = {} if look is True else look
    if not isinstance(r, dict):
        raise RostrumError(codes.BAD_ARGUMENT, "run_script", "look", "is true or an object of render_mix's arguments",
                           hint='{"look": {"name": "cue", "expect": [{"at": 31.5, "kind": "hit"}]}}')
    wrong = sorted(set(r) - set(allowed))
    if wrong:
        raise RostrumError(codes.BAD_ARGUMENT, "run_script", "look", f"has {', '.join(wrong)}, which render_mix does not take", sorted(allowed))
    return {**({"item": item} if item else {}), **r}


def _rendered(ctx, rargs) -> Reply:
    """render_mix run as itself, waited for: its finished reply, or where the job is when the wait runs out."""
    try:
        started = ctx.tools.get("render_mix").fn(ctx, rargs)
        job = ctx.jobs.wait(started.data["job_id"], WAIT_S)
        if job.status in ("done", "failed", "cancelled"):
            return outcome(job, "run_script › look")
    except RostrumError as e:
        e.hint = "The script ran and is in the song; only the render failed. " + (e.hint or "")
        raise
    return Reply(f"The render is still running after {WAIT_S:g} s: job {job.id}. Ask inspect_job {{\"job\": \"{job.id}\"}} "
                 "for its listening check.", job.state())


def after_run(ctx, doc, look, reply: Reply) -> Reply:
    """App.script_look: the merge's reply, then the render and its listening check."""
    r = _rendered(ctx, render_args(look, _allowed(ctx), getattr(doc, "item_id", None)))    # ctx.tool is run_script: a check, never refused for open faults
    said = r.summary.replace(session_clock.AGAIN, AGAIN)
    return Reply(f"{reply.summary}\n{said}", {**reply.data, "look": r.data}, [*reply.files, *r.files], [*reply.images, *r.images],
                 [*reply.warnings, *r.warnings], reply.changed, r.faults)


def with_look(runtime) -> None:
    """Sound's `look` schema and lead in run_script's description (the shared one speaks of stills), and a wrong
    `look` refused before the script runs."""
    old = runtime.tools.get("run_script")

    def run_script(ctx, args):
        if args.get("look") not in (None, False):
            render_args(args["look"], _allowed(ctx))
        return old.fn(ctx, args)
    schema = copy.deepcopy(old.schema)
    schema.setdefault("properties", {})["look"] = SCHEMA
    runtime.tools._tools["run_script"] = dataclasses.replace(old, fn=run_script, schema=schema,
                                                             description=LEAD + old.description.replace(LOOK_LEAD, ""))
