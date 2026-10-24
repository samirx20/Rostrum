"""`tempo.fit_bar` (land a bar on a marker: score to picture, DESIGN.md §3.12). One operation, one undo step; the
screen's "Land a bar here" calls it, as an agent does.
"""
from __future__ import annotations

from rostrum_core import Param, codes

from . import markers, meter, tempo
from .registry import REGISTRY

MARKER = Param.text("marker", required=True, label="Marker", group="Fit",
                    help='The marker the bar should start on, by name ("logo lands").')
BAR = Param.number("bar", required=True, integer=True, min=2, max=999, label="Bar", group="Fit",
                   help="The bar (counted from 1) that starts on the marker.")


@REGISTRY.operation("tempo.fit_bar", "Change the tempo so a bar starts exactly on a marker: the tempo in force at "
                    "that bar (the song's, or the tempo change before it) is set; everything written in beats "
                    "follows.", params=[MARKER, BAR], label="Start a bar on a marker")
def fit_bar(ctx, targets, args):
    root, name = ctx.doc, str(args["marker"]).lstrip("#")
    marks = markers.by_name(root)
    if markers.key(name) not in marks:
        ctx.fail(codes.NOT_FOUND, f'marker "{name}"', "is not a marker in this song or project")
    at = marks[markers.key(name)][1].get("at", 0)
    if isinstance(at, dict) or isinstance(at, str):
        ctx.fail(codes.BAD_ARGUMENT, f'marker "{name}"', "is placed on a beat, so it moves with the tempo",
                 hint="Fit a bar to a marker placed in seconds (the picture's, or one from 2D).")
    t = markers.time_of(root, name)
    beat = meter.bar_start(root, int(args["bar"]))
    segs = tempo.segments(root)
    i = max(k for k, s in enumerate(segs) if s[0] <= beat + 1e-9)
    b0, _, s0, *_ = segs[i]
    if any(s[3] != s[1] for s in segs[max(0, i - 1):i + 1]):
        ctx.fail(codes.BAD_ARGUMENT, f"bar {args['bar']}", "sits in or after a tempo ramp, so no single tempo decides "
                 "where it lands", hint="Turn the ramp off first, or choose a bar after a held tempo.")
    if t <= s0 + 1e-6 or beat <= b0:
        ctx.fail(codes.BAD_ARGUMENT, f"bar {args['bar']}", f"can't start on \"{name}\" ({t:.2f} s): a tempo change "
                 "before it already decides where it lands", hint="Choose a later bar, or a later marker.")
    bpm = round(60.0 * (beat - b0) / (t - s0), 6)     # exact enough that the bar lands within a microsecond
    if not 20 <= bpm <= 400:
        ctx.fail(codes.BAD_ARGUMENT, f"bar {args['bar']}", f"would need {bpm:.0f} bpm to land on \"{name}\"",
                 hint="Choose another bar: one that needs a tempo between 20 and 400.")
    if i == 0:
        ctx.set("root", "tempo", bpm)
        return
    change = min((c for c in root.get("tempos", [])), key=lambda c: abs(_beat_of(root, c) - b0))
    ctx.set(change["id"], "bpm", bpm)


def _beat_of(root, c):
    return float(c["at"]["beat"]) if isinstance(c["at"], dict) else tempo.beat_at(root, float(c["at"]))

