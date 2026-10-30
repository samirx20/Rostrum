"""Information an agent did not ask for but needs to keep going, never a gate (adopted from the tool experiment's loop
variant, 2026-10-30: with it agents used more of their time and made no failed calls).

- Every reply ends with the session's clock: time since the session started (the server starts with it, so the first
  script's writing counts, and RostrumSound's clock, started the same way, agrees), how much of it went to exports,
  calls, and time left when ROSTRUM_SESSION_BUDGET_MIN is set (agents that cannot see the time stop early believing it
  is up: one stopped at 8 of 40 minutes).
- render_film's reply carries a review sheet of the delivered film (a frame every 2.5 s) and the review notes for those
  frames, so the first look at the finished film costs nothing.
"""
from __future__ import annotations

import dataclasses
import os
import time

REVIEW_EVERY = 2.5


def _said(seconds: float) -> str:
    m, s = divmod(round(seconds), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def wrap(tools, review) -> None:
    """Every tool's reply gets the clock line; render_film's also the review sheet and notes
    (`review(name) -> (png, times, notes)`)."""
    started, calls, exporting = time.monotonic(), [0], [0.0]
    budget = float(os.environ["ROSTRUM_SESSION_BUDGET_MIN"]) if os.environ.get("ROSTRUM_SESSION_BUDGET_MIN") else None
    for t in tools.all():
        fn = t.fn

        def wrapped(ctx, args, fn=fn, name=t.name):
            calls[0] += 1
            t0 = time.monotonic()
            reply = fn(ctx, args)
            if name == "render_film":
                exporting[0] += time.monotonic() - t0
                png, times, notes = review(args["name"])
                reply.images.append(png)
                reply.summary += (f" Review sheet of the delivered film attached: a frame every {REVIEW_EVERY:g} s "
                                  f"({times[0]:g}–{times[-1]:g} s).")
                if notes:
                    reply.summary += " Seen in those frames: " + "; ".join(notes) + "."
            used = time.monotonic() - started
            spent = f" ({_said(exporting[0])} of it exporting)" if exporting[0] >= 1 else ""
            left = f" · {_said(max(0.0, budget * 60 - used))} of your {budget:g} min left" if budget else ""
            reply.summary += f"\nSession {_said(used)}{spent} · {calls[0]} calls{left}"
            return reply

        tools._tools[t.name] = dataclasses.replace(t, fn=wrapped)
