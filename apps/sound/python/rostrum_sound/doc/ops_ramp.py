"""`note.ramp_velocity`: Ramp velocity…, a crescendo or a fade across the selection in one step. Every selected note
gets a velocity set by where it starts between the first and the last start: `start` on the first, `end` on the last,
the ones between on a straight line (`curve` "linear") or an S (`curve` "ease": slow off the start, slow into the end).
Notes that start together (a chord) get the same velocity.

Found by the hand-made cue (production round 1, hand #24): a 4-bar brass crescendo was 4 box-selects and 4 typed
velocities per track, and the velocity strip was too short to draw it.
"""
from __future__ import annotations

from rostrum_core import Param, codes

from . import values as V
from .registry import REGISTRY
from .select_time import start_of

START = V.N("start", 0, 1, "Ramp", label="Start", display="percent", default=0.5,
            help="Velocity of the first note (0 … 1; the screen shows %).")
END = V.N("end", 0, 1, "Ramp", label="End", display="percent", default=0.9,
          help="Velocity of the last note (0 … 1). Higher than `start`: a crescendo; lower: a fade.")
CURVE = Param.choice("curve", ["linear", "ease"], default="linear", group="Ramp", label="Curve", importance="secondary",
                     help="linear: a straight line from start to end. ease: an S, slow off the start and slow into the end.")


def shape(u: float, curve: str) -> float:
    """0 … 1 along the ramp at `u` (0 … 1 of the way in time)."""
    return u * u * (3 - 2 * u) if curve == "ease" else u


@REGISTRY.operation("note.ramp_velocity", "Ramp the velocity across the target notes (ids, or a range: "
                    '{"track": "brass", "from": {"bar": 9}, "to": {"bar": 13}}): the first note gets `start`, the last '
                    "`end` (0 … 1), each one between by where it starts, on a straight line (`curve` linear) or an S "
                    "(`curve` ease). A crescendo: start below end; a fade: start above end. Notes that start together get "
                    "the same velocity. Needs notes at two or more times. One undo step.",
                    target="note", params=[START, END, CURVE], label="Ramp velocity", importance="secondary")
def ramp_velocity(ctx, targets, args):
    root = ctx.doc
    a, b, curve = args.get("start", 0.5), args.get("end", 0.9), args.get("curve", "linear")
    at = {t: start_of(root, ctx.item(t)) for t in dict.fromkeys(targets)}
    first, last = min(at.values(), default=0.0), max(at.values(), default=0.0)
    if last - first < 1e-6:
        ctx.fail(codes.BAD_ARGUMENT, "targets", "all start at the same time: a ramp needs notes at two or more times",
                 hint="Select notes across the stretch to ramp.", plain="Ramp velocity needs notes at two or more times.")
    for t, s in at.items():
        ctx.set(t, "vel", round(a + (b - a) * shape((s - first) / (last - first), curve), 3))
