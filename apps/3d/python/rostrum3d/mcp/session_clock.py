"""A clock for the agent: every reply of the rostrum-3d server ends with one short line (how long the session has run, how many
calls, whether the picture was looked at since the last edit, whether the last video was looked at), and after a video
the line counts how many look-fix-export passes the time left allows. Agents that cannot see the time quit early believing it
is up (the 3D benchmark's agents used about 2 of their 12 minutes); this is the time and the facts, never a verdict.

The session starts at the first tool call. ROSTRUM_SESSION_BUDGET_MIN (minutes; the same variable as rostrum-2d), when set, adds
how many minutes are left. The server of a bench sets it; without it the line has the time used but no time left."""
from __future__ import annotations

import dataclasses
import os
import time

from rostrum_core.mcp import Reply

EXPORTS = {"render_video"}                  # a finished video: the agent should look at the shot again and fix
PASS_S = 150.0                              # one look-fix-export pass besides the export itself: looks, a script change, thinking
DEFAULT_EXPORT_S = 60.0                     # a pass's export when none was measured yet


def said_time(seconds: float) -> str:
    m, s = divmod(round(seconds), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def passes_left(left_s: float, export_s: float | None) -> int:
    """How many more look-fix-export passes `left_s` seconds allow: each is the measured export plus PASS_S of looking and fixing."""
    return max(0, int(left_s // ((export_s or DEFAULT_EXPORT_S) + PASS_S)))


class Clock:
    def __init__(self, now=time.monotonic, budget_min: float | None = None):
        self.now, self.budget_min = now, budget_min
        self.started: float | None = None
        self.calls = self.edits_since_look = 0
        self.looked = False
        self.exported = self.export_looked = False
        self.export_s: float | None = None          # how long the last video took (render_video's `seconds`, probe included)

    def begin(self) -> None:
        self.started = self.started if self.started is not None else self.now()
        self.calls += 1

    def elapsed(self) -> float:
        return self.now() - self.started if self.started is not None else 0.0

    def left(self) -> float | None:
        return None if self.budget_min is None else self.budget_min * 60 - self.elapsed()

    def noted(self, tool: str, args: dict, reply: Reply) -> None:
        """Take in one answered call: an edit, a look, a finished video (it arrives as inspect_job's result, labelled render_video)."""
        data = reply.data if isinstance(reply.data, dict) else {}
        if reply.changed is not None:
            self.edits_since_look += 1
        if tool.startswith("look_"):
            self.looked, self.edits_since_look = True, 0
            self.export_looked = self.exported
        result = data.get("result")
        if tool == "inspect_job" and str(data.get("label", "")).split(" ")[0] in EXPORTS and data.get("status") == "done" \
                and isinstance(result, dict) and isinstance(result.get("seconds"), (int, float)):
            self.exported, self.export_looked = True, False
            self.export_s = float(result["seconds"])

    def line(self) -> str:
        parts = [f"Session {said_time(self.elapsed())} of real time since your first call (your thinking included)",
                 f"{self.calls} call{'s' * (self.calls != 1)}"]
        if not self.looked:
            parts.append("no look at the picture yet")
        elif self.edits_since_look:
            parts.append(f"last look at the picture {self.edits_since_look} edit{'s' * (self.edits_since_look != 1)} ago")
        else:
            parts.append("the picture was looked at since your last edit")
        if self.exported and not self.export_looked:
            parts.append("the last video has not been looked at (look_frame what \"sheet\", look_motion)")
        left = self.left()
        if left is not None:
            parts.append(f"{said_time(left)} of your {self.budget_min:g} min left" + (" (time to look and refine)" if left > 60 else "")
                         if left > 0 else f"your {self.budget_min:g} min are used")
            if self.exported and (n := passes_left(left, self.export_s)):
                parts.append(f"enough for about {n} more pass{'es' * (n != 1)} of look, fix and export")
        return " · ".join(parts)


def _budget() -> float | None:
    raw = os.environ.get("ROSTRUM_SESSION_BUDGET_MIN", "").strip()
    try:
        return float(raw) if raw and float(raw) > 0 else None
    except ValueError:
        return None


def with_clock(runtime, clock: Clock | None = None) -> Clock:
    """Every tool's reply ends with the clock line."""
    clock = clock or Clock(budget_min=_budget())
    for name, tool in list(runtime.tools._tools.items()):
        runtime.tools._tools[name] = dataclasses.replace(tool, fn=_wrapped(tool, clock))
    getattr(runtime, "waited", []).append(_finished(clock))
    return clock


def _finished(clock: Clock):
    """A render's finished reply (the server waited for its job, job_wait): taken in as inspect_job's, with its line."""
    def fn(ctx, args, reply):
        clock.noted("inspect_job", args, reply)
        reply.summary = f"{reply.summary}\n{clock.line()}"
        return reply
    return fn


def _wrapped(tool, clock: Clock):
    def fn(ctx, args):
        clock.begin()
        reply = tool.fn(ctx, args)
        clock.noted(ctx.tool, args, reply)
        reply.summary = f"{reply.summary}\n{clock.line()}"
        return reply
    return fn
