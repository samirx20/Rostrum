"""A clock for the agent: every reply of the rostrum-2d server ends with one short line (how long the session has run, how many
calls, how long since the picture was last looked at), and inspect_project what "session" says what is still unchecked.
Agents that cannot see the time stop early believing it is up; this is the time and the facts, never a verdict.

The session starts at the first tool call. ROSTRUM_SESSION_BUDGET_MIN (minutes), when set, adds how many are left."""
from __future__ import annotations

import dataclasses
import os
import time

from rostrum_core.mcp import Reply
from rostrum_core.mcp.tools import _schema_of

SEES_PICTURE = {"look_motion", "look_drawing", "look_painting"}
EXPORTS = {"render_video", "render_export"}        # an export the agent should look at (render_export: an mp4's reply has `quiet_stretches`)
KINDS = {"full-size frame": "a full-size single frame (look_frame time)", "motion": "the motion (look_motion)"}     # named after an export until done     # looks that reset "edits since the last look"
PASS_S = 150.0                # a look-fix-export pass besides the export itself: looks, a script change, thinking
MOMENT = 2.0                  # a looked-at time stands for this many seconds either side of it
SESSION_ARG = {"what": {"enum": ["project", "session"], "default": "project", "description":
               '"project" (default): the project\'s items. "session": the clock: time since your first call, calls, edits since you last '
               "looked at the picture, the times of the piece you have never looked at (a look at a time covers 2 s either side), whether the "
               "export has been looked at, and the stretches the last empty check named."}}


def said_time(seconds: float) -> str:
    m, s = divmod(round(seconds), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def _merged(spans: list[tuple[float, float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


class Clock:
    def __init__(self, now=time.monotonic, budget_min: float | None = None):
        self.now, self.budget_min = now, budget_min
        self.started: float | None = None
        self.calls = self.edits = self.edits_since_look = 0
        self.looked = False
        self.covered: list[tuple[float, float]] = []
        self.exported = self.export_looked = False
        self.export_s: float | None = None          # how long the last export took (render_video's `seconds`)
        self.quiet: list[str] = []
        self.seen: set[str] = set()

    def begin(self) -> None:
        self.started = self.started if self.started is not None else self.now()
        self.calls += 1

    def elapsed(self) -> float:
        return self.now() - self.started if self.started is not None else 0.0

    def noted(self, tool: str, args: dict, reply: Reply) -> None:
        """Take in one answered call: an edit, a look (with the times it showed), a render, an empty check."""
        data = reply.data if isinstance(reply.data, dict) else {}
        label = str(data.get("label", "")).split(" ")[0]       # a finished job answers as inspect_job; its label names the tool
        who = tool if tool != "inspect_job" else label
        payload = data["result"] if isinstance(data.get("result"), dict) else data
        if reply.changed is not None:
            self.edits += 1
            self.edits_since_look += 1
        if who in EXPORTS and (who == "render_video" or "quiet_stretches" in payload or args.get("format") == "mp4"):
            self.exported = True
            self.export_s = payload.get("seconds") if isinstance(payload.get("seconds"), (int, float)) else self.export_s
            self.export_looked = self.export_looked and tool not in EXPORTS          # a new render: not looked at yet
        if who == "look_frame" and "video" in payload:
            self.export_looked = True
        elif who == "look_frame" and ("time" in payload or "times" in payload):
            self.looked, self.edits_since_look = True, 0
            if "times" not in payload:
                self.seen.add("full-size frame")
            self.covered += [(t - MOMENT, t + MOMENT) for t in payload.get("times") or [payload["time"]]]
        elif who in SEES_PICTURE and data.get("status", "done") == "done":
            self.looked, self.edits_since_look = True, 0
            if who == "look_motion":
                self.seen.add("motion")
        rows = payload.get("stretches") or payload.get("quiet_stretches")
        if who in ("look_frame", "render_video") and rows is not None:
            self.quiet = [r["text"] for r in rows]

    def unlooked(self, span: float) -> list[list[float]]:
        """The stretches of 0..span that no look covers."""
        gaps, at = [], 0.0
        for a, b in _merged(self.covered):
            if a > at + 1e-9:
                gaps.append([at, min(a, span)])
            at = max(at, b)
        return gaps + ([[at, span]] if at < span - 1e-9 else [])

    def left_said(self) -> str:
        """'Time left: 11 min (about 3 passes of fix and export). ' when there is a budget, else ''."""
        if self.budget_min is None:
            return ""
        left = self.budget_min * 60 - self.elapsed()
        if left <= 60:
            return "Time is up after this. "
        passes = int(left // ((self.export_s or 60.0) + PASS_S))
        return f"Time left: {round(left / 60)} min" + (f" (about {passes} more pass{'es' * (passes != 1)} of fix and export)" if passes else "") + ". "

    def line(self) -> str:
        parts = [f"Session {said_time(self.elapsed())} of real time since your first call (your thinking included)", f"{self.calls} call{'s' * (self.calls != 1)}"]
        if not self.looked:
            parts.append("no look at the picture yet")
        elif self.edits_since_look:
            parts.append(f"last look at the picture {self.edits_since_look} edit{'s' * (self.edits_since_look != 1)} ago")
        else:
            parts.append("the picture was looked at since your last edit")
        if self.exported and not self.export_looked:
            parts.append("the export has not been looked at")
        missing = [KINDS[k] for k in KINDS if k not in self.seen]
        if self.exported and missing and (self.budget_min is None or self.budget_min * 60 - self.elapsed() > 120):
            parts.append("not looked at yet: " + ", ".join(missing))
        if self.budget_min is not None:
            left = self.budget_min * 60 - self.elapsed()
            parts.append(f"{said_time(left)} of your {self.budget_min:g} min left" + (" (time to look and refine)" if left > 60 else "")
                         if left > 0 else f"your {self.budget_min:g} min are used")
            passes = int(left // ((self.export_s or 60.0) + PASS_S)) if self.exported else 0
            if passes >= 1:                  # agents stopped with two thirds of their time unused (fair 2D benchmark)
                parts.append(f"enough for about {passes} more pass{'es' * (passes != 1)} of look, fix and export")
        return " · ".join(parts)

    def facts(self, span: float | None) -> Reply:
        gaps = self.unlooked(span) if span else []
        todo = []
        if not self.looked:
            todo.append("no look at the picture yet (look_frame)")
        elif self.edits_since_look:
            todo.append(f"no look at the picture since your last {self.edits_since_look} edit{'s' * (self.edits_since_look != 1)}")
        if gaps:
            todo.append("times never looked at: " + ", ".join(f"{a:g}–{b:g} s" for a, b in gaps[:6]))
        if self.exported and not self.export_looked:
            todo.append('the export has not been looked at (look_frame what "sheet" with video = its path)')
        todo += [f"stretch named by the last empty check: {q}" for q in self.quiet[:4]]
        text = ("Still unchecked: " + "; ".join(todo) + ".") if todo else "Nothing is unchecked."     # the clock line follows (with_clock)
        return Reply(text, {"elapsed_s": round(self.elapsed(), 1), "calls": self.calls, "edits": self.edits, "edits_since_look": self.edits_since_look,
                            "unlooked_times": gaps, "export": {"rendered": self.exported, "looked": self.export_looked},
                            "empty_stretches": self.quiet, "budget_min": self.budget_min})


def _budget() -> float | None:
    raw = os.environ.get("ROSTRUM_SESSION_BUDGET_MIN", "").strip()
    try:
        return float(raw) if raw and float(raw) > 0 else None
    except ValueError:
        return None


def _span(ctx, args) -> float | None:
    try:
        comps = ctx.document(args.get("item")).data.get("comps", [])
    except Exception:       # noqa: BLE001  (no document open: the clock still answers, without the times)
        return None
    return max((c.get("duration", 5.0) for c in comps), default=None)


def with_clock(runtime, clock: Clock | None = None) -> Clock:
    """Every tool's reply ends with the clock line; inspect_project gains `what: "session"`."""
    clock = clock or Clock(budget_min=_budget())
    old = runtime.tools.get("inspect_project")
    spec, _ = _schema_of({**old.schema, "properties": {**old.schema["properties"], **SESSION_ARG}})

    def inspect_project(ctx, args):
        args = dict(args)
        if args.pop("what", "project") == "session":
            return clock.facts(_span(ctx, args))
        return old.fn(ctx, args)
    runtime.tools._tools["inspect_project"] = dataclasses.replace(
        old, fn=inspect_project, schema=spec,
        description=old.description + ' what "session": your clock (time since your first call, calls, edits since your last look at the picture, '
                                      "times never looked at, whether the export was looked at). Every reply of this server ends with the clock line.")
    for name, tool in list(runtime.tools._tools.items()):
        runtime.tools._tools[name] = dataclasses.replace(tool, fn=_wrapped(tool, clock))
    return clock


def _wrapped(tool, clock: Clock):
    def fn(ctx, args):
        clock.begin()
        reply = tool.fn(ctx, args)
        clock.noted(ctx.tool, args, reply)
        reply.summary = f"{reply.summary}{_fix_pass(ctx, args, reply, clock)}\n{clock.line()}"
        return reply
    return fn


def _fix_pass(ctx, args, reply: Reply, clock: Clock) -> str:
    """After a finished mp4 export (render_video, render_export): the minutes left and the film's weakest moments (review),
    as the next fix pass. In the fair benchmark agents ended the turn after one export believing every item was covered."""
    data = reply.data if isinstance(reply.data, dict) else {}
    payload = data["result"] if isinstance(data.get("result"), dict) else data
    if "quiet_stretches" not in payload or data.get("status", "done") != "done":
        return ""
    label = str(data.get("label", "")).split(" ")
    comp_id = label[1] if ctx.tool == "inspect_job" and len(label) > 1 else args.get("comp")
    try:
        from . import review
        from .pick import doc_and_comp
        doc, comp = doc_and_comp(ctx, {"comp": comp_id} if comp_id else {})
        said = review.after_export(doc.data, comp, payload.get("quiet_stretches") or [], payload.get("edge_cuts") or [])
    except Exception as e:      # noqa: BLE001  (the export stands; the review's failure is said, not hidden)
        said = f"(The review could not run: {e}; call look_review.)"
    return f"\n{clock.left_said()}{said}"
