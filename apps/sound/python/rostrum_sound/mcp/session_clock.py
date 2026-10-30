"""A clock for the agent: every reply of the rostrum-sound server ends with one short line (how long the session has run, how
many calls, what has changed since the last render, whether the last render was listened to), and a finished `render_mix`
with notes names the quick tools and says how much time is left. Agents that cannot see the time stop after a fifth of it
(the fair Sound benchmark: 3 of 15 minutes); this is the time and the facts, never a verdict. 2D's clock is the model
(apps/2d/.../session_clock.py): its looks are pictures, Sound's are the listening tools.

The session starts when the server does (with the agent's session, so the first script's writing counts and 2D's
clock, started the same way, agrees); a Clock made without a server starts at its first call. ROSTRUM_SESSION_BUDGET_MIN (minutes), when set, adds how many are left."""
from __future__ import annotations

import dataclasses
import os
import time

PASS_S = 150.0                  # a listen-fix-render pass besides the render itself: looks, a script change, thinking
LISTENS = {"look_loudness", "look_levels", "look_events", "look_spectrum", "look_stereo", "look_low_end", "look_clash",
           "look_beats", "look_pitch", "inspect_harmony"}     # the listening tools (the names behind look_sound / look_music)


def said_time(seconds: float) -> str:
    m, s = divmod(round(seconds), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


class Clock:
    def __init__(self, now=time.monotonic, budget_min: float | None = None):
        self.now, self.budget_min = now, budget_min
        self.started: float | None = None
        self.calls = self.renders = self.edits_since_render = self.listens_since_render = 0
        self.render_s: float | None = None          # how long the last render took

    def begin(self) -> None:
        self.started = self.started if self.started is not None else self.now()
        self.calls += 1

    def elapsed(self) -> float:
        return self.now() - self.started if self.started is not None else 0.0

    def left(self) -> float | None:
        return None if self.budget_min is None else self.budget_min * 60 - self.elapsed()

    def noted(self, tool: str, reply) -> None:
        """Take in one answered call: an edit, a listen, a finished render (a job answers as inspect_job; its label names the tool)."""
        data = reply.data if isinstance(reply.data, dict) else {}
        if getattr(reply, "changed", None) is not None:
            self.edits_since_render += 1
        if tool in LISTENS and data.get("status", "done") == "done":
            self.listens_since_render += 1
        if tool == "inspect_job" and str(data.get("label", "")).startswith("render ") and data.get("status") == "done":
            self.renders += 1
            self.edits_since_render = self.listens_since_render = 0
            result = data.get("result") if isinstance(data.get("result"), dict) else {}
            if isinstance(result.get("renderSeconds"), (int, float)):
                self.render_s = result["renderSeconds"]

    def passes(self, render_s: float | None = None) -> int:
        """How many more renders the time left holds (0 with no budget)."""
        left = self.left()
        return 0 if left is None or left <= 0 else int(left // ((render_s or self.render_s or 30.0) + PASS_S))

    def line(self) -> str:
        parts = [f"Session {said_time(self.elapsed())} of real time since it started (your thinking included)",
                 f"{self.calls} call{'s' * (self.calls != 1)}"]
        if self.renders:
            parts.append(f"{self.renders} render{'s' * (self.renders != 1)}, {self.edits_since_render} edit{'s' * (self.edits_since_render != 1)} since the last"
                         + ("" if self.listens_since_render else ", not listened to yet"))
        left = self.left()
        if left is not None:
            parts.append(f"{said_time(left)} of your {self.budget_min:g} min left" + (" (time to listen and refine)" if left > 60 else "")
                         if left > 0 else f"your {self.budget_min:g} min are used")
            if self.passes() >= 1:
                parts.append(f"time for about {self.passes()} more render{'s' * (self.passes() != 1)}")
        return " · ".join(parts)


AGAIN = "and render_mix again to the same name"     # run_script's render says its own way round (script_render.py)


def fix_pass(clock: Clock | None, render_s: float | None = None) -> str:
    """The closing line of a render with notes: the quick tools for hearing a moment again, and the time left. Facts
    only: what to change, if anything, is the agent's call."""
    said = ("To hear one moment again without a full render: render_audition {at: \"#marker\"} or {from: {bar: n}, to: {bar: m}} "
            "(about a second, read as numbers; look: true adds its picture).")
    left = clock.left() if clock else None
    if left is None:
        return said
    if left <= 0:
        return said + f" Your {clock.budget_min:g} min are used."
    n = clock.passes(render_s)
    return said + f" {said_time(left)} of your {clock.budget_min:g} min are left" + (
        f": time for about {n} more render{'s' * (n != 1)}." if n else ".")


def _budget() -> float | None:
    raw = os.environ.get("ROSTRUM_SESSION_BUDGET_MIN", "").strip()
    try:
        return float(raw) if raw and float(raw) > 0 else None
    except ValueError:
        return None


def with_clock(runtime, clock: Clock | None = None) -> Clock:
    """Every tool's reply ends with the clock line; the clock is `app.state.clock`, where render_mix reads it for its fix pass."""
    clock = clock or Clock(budget_min=_budget())
    clock.started = clock.now() if clock.started is None else clock.started      # the server starts with the session
    runtime.app.state.clock = clock
    for name, tool in list(runtime.tools._tools.items()):
        runtime.tools._tools[name] = dataclasses.replace(tool, fn=_wrapped(tool, clock))
    getattr(runtime, "waited", []).append(_finished(clock))
    return clock


def _finished(clock: Clock):
    """A render's finished reply (the server waited for its job, job_wait): taken in as inspect_job's, with its line."""
    def fn(ctx, args, reply):
        clock.noted("inspect_job", reply)
        reply.summary = f"{reply.summary}\n{clock.line()}"
        return reply
    return fn


def _wrapped(tool, clock: Clock):
    def fn(ctx, args):
        clock.begin()
        reply = tool.fn(ctx, args)
        clock.noted(ctx.tool, reply)
        reply.summary = f"{reply.summary}\n{clock.line()}"
        return reply
    return fn
