"""render_export waits for its own job, so the finished reply (the file, the checks it was asked for) comes back once,
without polling: by default as long as the calling program lets a call run (rostrum_core job_wait.budget: 25 min for
Claude Code, ~50 s for a program we don't know); past it, how far it is, and inspect_job waits again. The server does
the waiting (job_wait.finish, outside the one-writer lock); `wait_s` only says how long. `wait_s` 0 answers with the job
id at once (an mp4 is drawn from a copy of the document taken now). In the benchmark one agent spent 22 calls on
inspect_job for its renders. A failed or stopped job is an error, as inspect_job's is (jobs.outcome)."""
from __future__ import annotations

import dataclasses

from rostrum_core.mcp import job_wait
from rostrum_core.mcp.tools import _schema_of

TOOLS = ("render_export",)
MOST_S = job_wait.MOST_S
WAIT = {"wait_s": {"type": "number", "minimum": 0, "maximum": MOST_S,
                   "description": "Seconds to wait for the file in this call. Default: until it is finished (as long as your program lets a "
                                  "call run; past it, inspect_job waits again); 0: the job id at once, it renders in the background."}}


def with_wait(runtime) -> None:
    for name in TOOLS:
        old = runtime.tools.get(name)
        spec, _ = _schema_of({**old.schema, "properties": {**old.schema["properties"], **WAIT}})
        runtime.tools._tools[name] = dataclasses.replace(old, fn=_waiting(old.fn), schema=spec)


def _waiting(fn):
    def run(ctx, args):
        wait_s = args.get("wait_s", job_wait.budget(getattr(ctx, "who", None)))
        reply = fn(ctx, {k: v for k, v in args.items() if k != "wait_s"})
        job_id = reply.data.get("job_id") if isinstance(reply.data, dict) else None
        if job_id and wait_s <= 0:
            reply.summary = (f"Exporting in the background (job {job_id}), from the document as it is now: later edits are "
                             f"not in this file. Keep working; inspect_job {{\"job_id\": \"{job_id}\"}} waits for it and gives "
                             "the finished reply (wait_s 0: how far it is).")
        if job_id and hasattr(ctx, "wait_for"):
            ctx.wait_for.append(wait_s)        # the server waits, after this call lets go of the document
        return reply
    return run
