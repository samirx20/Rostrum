"""`note.strum` (sound-pro-workflows SPEC § 3.10): Chord ▾ › Strum…, each tone of a chord starting a little after the
one below it (an up-strum from the top with a negative gap), like a guitar.

On each chord of the selection (`chords.py`, base B) the tones are re-spaced from the chord's earliest start, so
Strum on a strummed chord sets a new gap instead of stacking one on the other (gap 0 lines the chord up again).
Every tone keeps its end: its length shrinks by as much as its start moved. Times and lengths keep the form they
were written in (seconds, beats, a marker). A chord written as one note with a list of pitches gets its `strum`
field instead (the engine plays the same thing).
"""
from __future__ import annotations

from rostrum_core import Param, codes

from . import chords
from . import fields as FD
from .registry import REGISTRY
from .select_time import at_seconds, end_of, note_dur

GAP = Param.number("gap", min=-200, max=200, default=30, group="Strum", unit="ms", label="Gap",
                   help="How long after the tone below each tone starts, in ms (30 = a quick strum). Negative: an up-strum, "
                        "from the top note down. 0 lines the chord up again.")
SOFTEN = Param.number("soften", min=0, max=0.5, default=0.1, group="Strum", importance="secondary", label="Soften",
                      display="percent", help="How much softer the last tone plays than the first (0.1 = 10 %); the ones "
                                              "between in steps. Measured from the first tone, so strumming again never "
                                              "stacks it. 0 leaves velocities as they are.")
SHORTEST = 0.010            # seconds: a tone keeps at least this much after its new start


@REGISTRY.operation("note.strum", "Strum each chord of the selection: each tone starts `gap` ms after the one below it "
                    "(negative: from the top note, an up-strum) and keeps its end, so it gets shorter; `soften` makes the "
                    "last tone that much softer than the first (0.1 = 10 %), the ones between in steps. Strumming a "
                    "strummed chord re-spaces it from its earliest start (gap 0 lines it up again). A note with a list of "
                    "pitches gets its own strum field instead. Valid when the selection holds a chord of two or more "
                    "notes; fails (changing nothing) if a tone would start at or after its own end. The reply lists the "
                    "notes whose start, length and velocity changed.",
                    target="note", params=[GAP, SOFTEN], label="Strum", importance="secondary")
def strum(ctx, targets, args):
    gap, soften, root = args.get("gap", 30), args.get("soften", 0.1), ctx.doc
    plan = []
    for c in chords.need_chords(ctx, targets):
        if c["listed"]:
            plan.append((c["ids"][0], "strum", gap))
            continue
        order = c["ids"] if gap >= 0 else c["ids"][::-1]
        lead = ctx.item(order[0]).get("vel", FD.DEFAULTS["note"]["vel"])
        for i, t in enumerate(order):
            n = ctx.item(t)
            start, end = c["start"] + i * abs(gap) / 1000, end_of(root, n)
            if end - start < SHORTEST:
                ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', f"would start at or after its own end with a {abs(gap):g} ms gap",
                         hint="Use a smaller gap, or longer notes.", plain="The chord is too short for that gap.")
            plan.append((t, "at", at_seconds(ctx, n, start)))
            dur = note_dur(root, n, start, end)
            if dur is not None:
                plan.append((t, "dur", dur))
            if soften and len(order) > 1:
                plan.append((t, "vel", round(lead * (1 - soften * i / (len(order) - 1)), 3)))
    for t, field, value in plan:                       # all checked first: a failure changes nothing
        ctx.set(t, field, value)
