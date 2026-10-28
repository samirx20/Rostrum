"""run_script's `render`: write the whole piece, render it and read the listening check in one call.

Round 2's agents made many small calls, used about 2 of their 15 minutes and made whole-piece mistakes no single call
caught. With `render` the loop is one call: the script merges, then render_mix itself runs (the one render path: its
own function, with the arguments given), the call waits for the job (up to WAIT_S) and the reply is the script's line
followed by render_mix's listening summary: loudness, the weakest asked moments with their fixes, the files. A script
that fails renders nothing; a render argument render_mix doesn't take is refused before the script runs."""
from __future__ import annotations

import copy
import dataclasses

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply
from rostrum_core.mcp.jobs import outcome

from . import session_clock

WAIT_S = 150.0
AGAIN = "and run_script again with the edited source, the same name and render"
SCHEMA = {"description": "Render the mix after the script merges and answer with render_mix's listening check: true, or an "
                         "object with render_mix's arguments ({\"name\": \"Late Set\", \"folder\": \"C:/out\", \"expect\": "
                         "[{\"at\": 31.5, \"kind\": \"stop\"}, {\"kind\": \"tempo\", \"bpm\": 132}]}). The call waits for the "
                         "render (up to 150 s; longer: the reply names the job for inspect_job). A failing script renders nothing."}
DESCRIBE = ("The loop: write the whole piece as one script with `render` (true, or render_mix's arguments with `expect`), read "
            "the reply's weakest moments, edit the script and run it again under the same name with `render`, until the list is clean.")


def _render_args(args, allowed) -> dict | None:
    """The render_mix arguments `render` asks for (None: no render); a wrong one answers before the script runs."""
    r = args.get("render")
    if r in (None, False):
        return None
    if r is True:
        r = {}
    if not isinstance(r, dict):
        raise RostrumError(codes.BAD_ARGUMENT, "run_script", "render", "is true or an object of render_mix's arguments", hint='{"render": {"name": "cue", "expect": [{"at": 31.5, "kind": "hit"}]}}')
    wrong = sorted(set(r) - set(allowed))
    if wrong:
        raise RostrumError(codes.BAD_ARGUMENT, "run_script", "render", f"has {', '.join(wrong)}, which render_mix does not take", sorted(allowed))
    return {**({"item": args["item"]} if args.get("item") else {}), **r}


def _rendered(ctx, render_mix, rargs) -> Reply:
    """render_mix run as itself, waited for: its finished reply, or where the job is when the wait runs out."""
    try:
        started = render_mix.fn(ctx, rargs)
        job = ctx.jobs.wait(started.data["job_id"], WAIT_S)
        if job.status in ("done", "failed", "cancelled"):
            return outcome(job, "run_script › render")
    except RostrumError as e:
        e.hint = "The script ran and is in the song; only the render failed. " + (e.hint or "")
        raise
    return Reply(f"The render is still running after {WAIT_S:g} s: job {job.id}. Ask inspect_job {{\"job\": \"{job.id}\"}} "
                 "for its listening check.", job.state())


def with_render(runtime) -> None:
    old, render_mix = runtime.tools.get("run_script"), runtime.tools.get("render_mix")
    allowed = set(render_mix.schema.get("properties") or {}) - {"what"}     # the mix, not the MIDI file

    def run_script(ctx, args):
        rargs = _render_args(args, allowed)
        out = old.fn(ctx, {k: v for k, v in args.items() if k != "render"})
        if rargs is None:
            return out
        r = _rendered(ctx, render_mix, rargs)
        said = r.summary.replace(session_clock.AGAIN, AGAIN)
        return Reply(f"{out.summary}\n{said}", {**out.data, "render": r.data}, [*out.files, *r.files], [*out.images, *r.images],
                     [*out.warnings, *r.warnings], out.changed)
    schema = copy.deepcopy(old.schema)
    schema.setdefault("properties", {})["render"] = SCHEMA
    runtime.tools._tools["run_script"] = dataclasses.replace(old, fn=run_script, schema=schema, description=f"{old.description} {DESCRIBE}")
