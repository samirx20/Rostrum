"""The 'loop' variant of the markup tools (ROSTRUM2D_MARKUP_LOOP=1; the tool experiment, 2026-10-30): information an
agent did not ask for but needs to keep going, never a gate.

- Every reply ends with the session's clock: time used, calls, and time left when ROSTRUM_SESSION_BUDGET_MIN is set
  (agents that cannot see the time stop early believing it is up: one stopped at 8 of 40 minutes).
- render_film's reply carries a review sheet of the delivered film (a frame every 2.5 s), so the first look at the
  finished film costs nothing.
"""
from __future__ import annotations

import dataclasses
import os
import time

from rostrum_core.mcp import Reply

REVIEW_EVERY = 2.5


def on() -> bool:
    return os.environ.get("ROSTRUM2D_MARKUP_LOOP") == "1"


def _said(seconds: float) -> str:
    m, s = divmod(round(seconds), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def wrap(tools, review) -> None:
    """Every tool's reply gets the clock line; render_film's also the review sheet (`review(name) -> (png, times)`)."""
    started, calls = [None], [0]
    budget = float(os.environ["ROSTRUM_SESSION_BUDGET_MIN"]) if os.environ.get("ROSTRUM_SESSION_BUDGET_MIN") else None
    for t in tools.all():
        fn = t.fn

        def wrapped(ctx, args, fn=fn, name=t.name):
            started[0] = started[0] if started[0] is not None else time.monotonic()
            calls[0] += 1
            reply = fn(ctx, args)
            if name == "render_film":
                png, times = review(args["name"])
                reply.images.append(png)
                reply.summary += (f" Review sheet of the delivered film attached: a frame every {REVIEW_EVERY:g} s "
                                  f"({times[0]:g}–{times[-1]:g} s).")
            used = time.monotonic() - started[0]
            left = f" · {_said(max(0.0, budget * 60 - used))} of your {budget:g} min left" if budget else ""
            reply.summary += f"\nSession {_said(used)} · {calls[0]} calls{left}"
            return reply

        tools._tools[t.name] = dataclasses.replace(t, fn=wrapped)
