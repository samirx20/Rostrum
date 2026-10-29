"""render_export waits for its own job in the same call (`wait_s`), so the finished reply (the file, the checks it was
asked for) comes back without polling; an mp4 by default does not wait (wait_s 0): it is drawn in the background from a
copy of the document taken now, and the agent keeps working and asks inspect_job when it wants the file. In the benchmark one agent spent 22 calls on inspect_job for its
renders. A failed or stopped job is an error here, as inspect_job's is (jobs.outcome); past `wait_s` the reply is the job's
progress and its id, never a success."""
from __future__ import annotations

import dataclasses
import time

from rostrum_core.mcp.jobs import MAX_WAIT_S, outcome
from rostrum_core.mcp.tools import _schema_of

TOOLS = ("render_export",)
WAIT_S, MOST_S = 120, 600
BACKGROUND = ("mp4",)        # formats that return the job id at once unless wait_s is given (and what "video", an mp4 too)
WAIT = {"wait_s": {"type": "number", "minimum": 0, "maximum": MOST_S,
                   "description": f"Seconds to wait for the file in this call; 0: the job id at once. Default: 0 for an mp4 (format mp4 or what \"video\": it renders in "
                                  f"the background while you keep working), {WAIT_S} for the other formats."}}


def with_wait(runtime) -> None:
    for name in TOOLS:
        old = runtime.tools.get(name)
        spec, _ = _schema_of({**old.schema, "properties": {**old.schema["properties"], **WAIT}})
        runtime.tools._tools[name] = dataclasses.replace(old, fn=_waiting(old.fn), schema=spec)


def _waiting(fn):
    def run(ctx, args):
        wait_s = args.get("wait_s", 0 if args.get("format") in BACKGROUND or args.get("what") == "video" else WAIT_S)
        reply = fn(ctx, {k: v for k, v in args.items() if k != "wait_s"})
        job_id = reply.data.get("job_id") if isinstance(reply.data, dict) else None
        if not job_id or wait_s <= 0:
            if job_id:
                reply.summary = (f"Exporting in the background (job {job_id}), from the document as it is now: later edits are "
                                 f"not in this file. Keep working; inspect_job {{\"job_id\": \"{job_id}\", \"wait_s\": 25}} "
                                 "says how far it is and gives the finished reply.")
            return reply
        until = time.monotonic() + wait_s
        job = ctx.jobs.get(job_id)
        while not job.finished.is_set() and (left := until - time.monotonic()) > 0:
            job = ctx.jobs.wait(job_id, min(left, MAX_WAIT_S))
        done = outcome(job, ctx.tool)           # failed / stopped: raised here, loudly
        if job.status not in ("done",):
            done.summary += f" Still running after {wait_s:g} s: inspect_job {{\"job_id\": \"{job_id}\", \"wait_s\": 25}} gives the finished reply."
        return done
    return run
