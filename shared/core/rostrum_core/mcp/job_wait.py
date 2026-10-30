"""A render answers once, when it is finished: every render_* tool that answers with a job id waits for that job in the
same call and answers with the finished reply (its files, its result), so an agent needs no inspect_job round trips.
`wait` on every look_* and render_* tool sets it: true or nothing (render_*) waits as long as the calling program lets a
call run (budget), a number waits that many seconds, false or 0 answers with the job id at once.

The budget is the calling program's limit with room to spare: Claude Code ("claude-code") ends a stdio tool call that
says nothing for 30 minutes (CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT, default 1 800 000 ms; its hard limit is ~27.8 hours), so
it waits 25 minutes; shared/mcp/call.py ("cli-agent") has no limit and waits as long; any other program ~50 s, under
the ~60 s many MCP clients allow a call (CONVENTIONS § 7). ROSTRUM_MCP_WAIT_S overrides it. Past the budget the reply
says the job is still running, how far, and to call inspect_job again, which waits the same way (never a success).

The server adds it (Runtime.call), so every app's tool has it, including ones an app wraps after registering. `wait`
is taken off the arguments before the tool sees them; the waiting happens outside the one-writer lock (a job never
touches the document). A failed or stopped job is an error, as inspect_job's is (jobs.outcome). A tool with its own
`wait_s` (2D render_export) waits by itself, with the same budget.
"""
from __future__ import annotations

import os
import time

from .jobs import MAX_WAIT_S, ENDED, outcome
from .reply import Reply

VERBS = ("look", "render")
LONG_S, SHORT_S, MOST_S = 1500, 50, 1800    # Claude Code / call.py; any other client; the most a number may ask
LONG_CLIENTS = ("claude-code", "cli-agent")  # Claude Code's clientInfo name; shared/mcp/call.py's default --name
ENV = "ROSTRUM_MCP_WAIT_S"
TRUE_S = SHORT_S                             # kept for callers that name it: `true` from a client we don't know
MARK = "x-rostrum-wait"                      # survives a copy (combine.py copies every part's arguments)
SCHEMA = {"type": ["boolean", "number"], "minimum": 0, "maximum": MOST_S, MARK: True,
          "description": "Wait for the job in this call. render_*: waits by default until the file is there (if it takes "
                         "longer than your program lets a call run, the reply says how far and inspect_job waits again); "
                         "true: the same; seconds: that long; false or 0: the job id at once."}


def budget(who=None) -> float:
    """How long a call from `who` (its client's name) may wait for a job, with room before its program gives up."""
    env = os.environ.get(ENV, "").strip()
    if env:
        try:
            return max(0.0, float(env))
        except ValueError:
            pass
    name = (getattr(who, "name", "") or "").lower()
    return float(LONG_S if name.startswith(LONG_CLIENTS) else SHORT_S)


def applies(name: str, schema: dict) -> bool:
    """A look_/render_ tool that has no `wait` argument of its own."""
    return name.split("_", 1)[0] in VERBS and "wait" not in schema.get("properties", {})


def by_default(name: str, schema: dict) -> bool:
    """A render_* tool waits when the agent said nothing; one with its own wait_s waits by itself."""
    return name.split("_", 1)[0] == "render" and "wait_s" not in schema.get("properties", {})


def with_wait_schema(name: str, schema: dict) -> dict:
    if not applies(name, schema):
        return schema
    return {**schema, "properties": {**schema.get("properties", {}), "wait": SCHEMA}}


def ours(schema: dict) -> bool:
    """The tool's `wait` is this one, or a copy of it (a combined tool's), not an argument of the tool's own."""
    return bool((schema.get("properties", {}).get("wait") or {}).get(MARK))


def take(args: dict | None, who=None, default: bool = False) -> tuple[dict | None, float]:
    """The arguments without `wait`, and how many seconds to wait (0: don't). `default`: wait the budget when not given."""
    if not isinstance(args, dict) or "wait" not in args:
        return args, (budget(who) if default else 0.0)
    rest = {k: v for k, v in args.items() if k != "wait"}
    w = args["wait"]
    if w is True:
        return rest, budget(who)
    if isinstance(w, (int, float)) and not isinstance(w, bool) and 0 <= w <= MOST_S:
        return rest, float(w)
    return (rest, 0.0) if w is False else (args, 0.0)   # out of range: left in, so the schema check names it


def until_ended(jobs, job_id: str, wait_s: float):
    """The job once it has ended, or as it is after wait_s seconds (jobs.wait waits at most MAX_WAIT_S at a time)."""
    until = time.monotonic() + wait_s
    job = jobs.get(job_id)
    while not job.finished.is_set() and (left := until - time.monotonic()) > 0:
        job = jobs.wait(job_id, min(left, MAX_WAIT_S))
    return job


def still_running(job, wait_s: float) -> str:
    """What a reply says when the budget ran out first: how far, and that the next call waits again."""
    pct = f", {round(100 * job.done / job.total)} %" if job.total and job.done is not None else ""
    return (f' Still rendering{pct} after {wait_s:g} s (this call answers before your program would give up on it): '
            f'call inspect_job {{"job_id": "{job.id}"}} to wait for it again; it answers once it is finished.')


def finish(jobs, reply: Reply, wait_s: float, where: str) -> Reply:
    """Wait for the reply's job (if any, and not ended) up to wait_s; the job's outcome then."""
    data = reply.data if isinstance(reply.data, dict) else {}
    job_id = data.get("job_id")
    if not job_id or wait_s <= 0 or data.get("status") in ENDED:
        return reply
    job = until_ended(jobs, job_id, wait_s)
    done = outcome(job, where)                    # failed / stopped: raised here, loudly
    done.warnings = [*reply.warnings, *(w for w in done.warnings if w not in reply.warnings)]
    if job.status != "done":
        done.summary += still_running(job, wait_s)
    return done
