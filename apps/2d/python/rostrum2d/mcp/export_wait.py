"""render_video and render_export wait for their own job in the same call (`wait_s`), so the finished reply (the file, its
checks, the weakest moments) comes back without polling. In the benchmark one agent spent 22 calls on inspect_job for its
renders. A failed or stopped job is an error here, as inspect_job's is (jobs.outcome); past `wait_s` the reply is the job's
progress and its id, never a success."""
from __future__ import annotations

import dataclasses
import time

from rostrum_core.mcp.jobs import MAX_WAIT_S, outcome
from rostrum_core.mcp.tools import _schema_of

TOOLS = ("render_video", "render_export")
WAIT_S, MOST_S = 120, 600
WAIT = {"wait_s": {"type": "number", "minimum": 0, "maximum": MOST_S, "default": WAIT_S,
                   "description": f"Wait up to this many seconds for the export to finish and get its finished reply in this call "
                                  f"(default {WAIT_S}: a 30 s 1080p film usually finishes inside it; up to {MOST_S}). 0: return the job id at once. "
                                  "Past it the reply is the job's progress: inspect_job with its job_id and wait_s. A failed export is an error, never a success."}}


def with_wait(runtime) -> None:
    for name in TOOLS:
        old = runtime.tools.get(name)
        spec, _ = _schema_of({**old.schema, "properties": {**old.schema["properties"], **WAIT}})
        runtime.tools._tools[name] = dataclasses.replace(old, fn=_waiting(old.fn), schema=spec)


def _waiting(fn):
    def run(ctx, args):
        wait_s = args.get("wait_s", WAIT_S)
        reply = fn(ctx, {k: v for k, v in args.items() if k != "wait_s"})
        job_id = reply.data.get("job_id") if isinstance(reply.data, dict) else None
        if not job_id or wait_s <= 0:
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
