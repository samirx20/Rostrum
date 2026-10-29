"""The brief's timed beats, declared once and checked on every export: render_export takes `beats` as look_frame
what "review" does. The last ones given for a composition are kept for the session (on the clock); look_frame what "review" checks them
when called without its own `beats`.
In the fair benchmark agents rarely called the review, so its beats never ran; the export they always call now carries them."""
from __future__ import annotations

import dataclasses

from rostrum_core.mcp.tools import _schema_of

from . import review_beats, tool_text
from .pick import doc_and_comp
from .review import BEATS

TOOLS = ("render_export", "look_frame")              # look_frame: only its what "review" takes beats
KEPT = " Kept for the session."


def with_beats(runtime, clock) -> None:
    """`beats` on the export tool and the review; either remembers the beats given, checked loudly before any job starts."""
    for name in TOOLS:
        old = runtime.tools.get(name)
        beats = old.schema["properties"].get("beats", {"description": tool_text.ARG["beats"]})
        props = {**old.schema["properties"], "beats": {**BEATS, "description": beats["description"] + KEPT}}
        spec, _ = _schema_of({**old.schema, "properties": props})
        runtime.tools._tools[name] = dataclasses.replace(old, fn=_remembering(old.fn, clock, name != "look_frame"), schema=spec)


def _remembering(fn, clock, strip: bool):
    def remember(ctx, args):
        if not strip and args.get("what") != "review":      # look_frame's other choices have no beats
            return fn(ctx, args)
        if "beats" in args:
            _, comp = doc_and_comp(ctx, args)
            review_beats.check(comp, args["beats"], ctx.tool)
            clock.beats[comp["id"]] = list(args["beats"])
            if strip:
                args = {k: v for k, v in args.items() if k != "beats"}
        elif not strip and (kept := clock.beats.get(doc_and_comp(ctx, args)[1]["id"])):
            args = {**args, "beats": kept}          # the review checks the beats an export was given
        return fn(ctx, args)
    return remember
