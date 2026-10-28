"""The brief's timed beats, declared once and checked on every export: render_video and render_export take `beats` as
look_review does. The last ones given for a composition are kept for the session (on the clock) and the export reply's
weakest moments (review.after_export, through session_clock) name a beat that never happens or comes at the wrong time.
In the fair benchmark agents rarely called look_review, so its beats never ran; the export they always call now carries them."""
from __future__ import annotations

import dataclasses

from rostrum_core.mcp.tools import _schema_of

from . import review_beats
from .pick import doc_and_comp
from .review import BEATS

TOOLS = ("render_video", "render_export", "look_review")
KEPT = " Kept for the session: every later export of this composition checks them (give [] to clear)."


def with_beats(runtime, clock) -> None:
    """`beats` on the export tools; any of TOOLS remembers the beats given, checked loudly before any job starts."""
    for name in TOOLS:
        old = runtime.tools.get(name)
        props = {**old.schema["properties"], "beats": {**BEATS, "description": BEATS["description"] + KEPT}}
        spec, _ = _schema_of({**old.schema, "properties": props})
        runtime.tools._tools[name] = dataclasses.replace(old, fn=_remembering(old.fn, clock, name != "look_review"), schema=spec)


def _remembering(fn, clock, strip: bool):
    def remember(ctx, args):
        if "beats" in args:
            _, comp = doc_and_comp(ctx, args)
            review_beats.check(comp, args["beats"], ctx.tool)
            clock.beats[comp["id"]] = list(args["beats"])
            if strip:
                args = {k: v for k, v in args.items() if k != "beats"}
        elif not strip and (kept := clock.beats.get(doc_and_comp(ctx, args)[1]["id"])):
            args = {**args, "beats": kept}          # look_review checks the beats an export was given
        return fn(ctx, args)
    return remember
