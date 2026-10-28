"""`wait` on every look_* and render_* tool: a tool that answers with a job id waits for that job in the same call and
answers with the finished reply (its files, its result), so an agent needs no inspect_job round trips.

The server adds it (Runtime.call), so every app's tool has it, including ones an app wraps after registering. `wait`
is taken off the arguments before the tool sees them; the waiting happens outside the one-writer lock (a job never
touches the document). A failed or stopped job is an error, as inspect_job's is (jobs.outcome); past the wait the reply
says plainly the job is still running, with its id: never a success.
"""
from __future__ import annotations

import time

from .jobs import MAX_WAIT_S, ENDED, outcome
from .reply import Reply

VERBS = ("look", "render")
TRUE_S, MOST_S = 50, 600                    # true: under the ~60 s many MCP clients allow a call (CONVENTIONS § 7)
SCHEMA = {"type": ["boolean", "number"], "minimum": 0, "maximum": MOST_S,
          "description": f"When the tool answers with a job: wait for it in this call and answer with the finished file. "
                         f"true waits up to {TRUE_S} s, a number that many seconds (up to {MOST_S}). Past it the reply says the job "
                         "is still running, with its job_id (inspect_job). A failed job is an error, never a success."}


def applies(name: str, schema: dict) -> bool:
    """A look_/render_ tool that has no `wait` argument of its own."""
    return name.split("_", 1)[0] in VERBS and "wait" not in schema.get("properties", {})


def with_wait_schema(name: str, schema: dict) -> dict:
    if not applies(name, schema):
        return schema
    return {**schema, "properties": {**schema.get("properties", {}), "wait": SCHEMA}}


def ours(schema: dict) -> bool:
    """The tool's `wait` is this one (not an argument of the tool's own)."""
    return schema.get("properties", {}).get("wait") is SCHEMA


def take(args: dict | None) -> tuple[dict | None, float]:
    """The arguments without `wait`, and how many seconds to wait (0: don't)."""
    if not isinstance(args, dict) or "wait" not in args:
        return args, 0.0
    rest = {k: v for k, v in args.items() if k != "wait"}
    w = args["wait"]
    if w is True:
        return rest, float(TRUE_S)
    if isinstance(w, (int, float)) and not isinstance(w, bool) and 0 <= w <= MOST_S:
        return rest, float(w)
    return (rest, 0.0) if w is False else (args, 0.0)   # out of range: left in, so the schema check names it


def finish(jobs, reply: Reply, wait_s: float, where: str) -> Reply:
    """Wait for the reply's job (if any, and not ended) up to wait_s; the job's outcome then."""
    data = reply.data if isinstance(reply.data, dict) else {}
    job_id = data.get("job_id")
    if not job_id or wait_s <= 0 or data.get("status") in ENDED:
        return reply
    until = time.monotonic() + wait_s
    job = jobs.get(job_id)
    while not job.finished.is_set() and (left := until - time.monotonic()) > 0:
        job = jobs.wait(job_id, min(left, MAX_WAIT_S))
    done = outcome(job, where)                    # failed / stopped: raised here, loudly
    done.warnings = [*reply.warnings, *(w for w in done.warnings if w not in reply.warnings)]
    if job.status != "done":
        done.summary += (f' Still running after {wait_s:g} s: call inspect_job {{"job_id": "{job_id}", "wait_s": 25}} '
                         "(or this tool again with wait) for the finished reply.")
    return done
