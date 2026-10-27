"""`note.pedal`: Chord ▾ › Pedal each chord. The track's sustain pedal (its `sustain` lane, CC 64) lifts on each new
chord of the selection and goes down again `catch` beats later (legato pedalling: the old harmony is let go, the new
one is caught), and lifts at the end of the last one. Written as steps (two points at one time, builder.sustain), in
beats, so a tempo change keeps it on the chords. The lane's points before the first chord and after the last are kept.

A "chord" is every group of notes that start together (chords.py's rule), single notes included: a bass note on a new
harmony is a change too. Found by the hand-made piano piece (production round): 38 lane clicks for 18 bars, and the
ramps between points let the pedal up half a beat early.
"""
from __future__ import annotations

from rostrum_core import Param, codes

from . import chords, ids, tempo, times
from . import lanes as LN
from .ops_mix import taken
from .registry import REGISTRY
from .select_time import end_of, start_of

CATCH = Param.number("catch", min=0.03, max=1, default=0.25, group="Pedal", unit="beats", label="Catch after",
                     help="How long after each chord starts the pedal goes down again, in beats (0.25 = a 16th): long "
                          "enough to let the old harmony go. Left out = 0.25.")


def _beat(root, sec):
    return {"beat": round(tempo.beat_at(root, sec), 4)}


@REGISTRY.operation("note.pedal", "Pedal each chord: on the selected notes' track(s), the sustain pedal lifts at each "
                    "new chord (notes that start together, a single note too) and goes down again `catch` beats later, "
                    "and lifts at the end of the last one. Written into the track's sustain lane as steps, in beats; "
                    "the lane's points before the first and after the last chord stay. Valid on notes.",
                    target="note", params=[CATCH], label="Pedal each chord", importance="secondary")
def pedal(ctx, targets, args):
    root, catch = ctx.doc, args.get("catch", 0.25)
    for t in targets:
        ctx.item(t)                                       # an unknown id fails loudly here
    by_track: dict[str, list[dict]] = {}
    for c in chords.of_selection(root, targets):
        by_track.setdefault(c["track"], []).append(c)
    for track, cs in by_track.items():
        if not LN.accepts(ctx.item(track), "sustain"):
            ctx.fail(codes.BAD_ARGUMENT, f'track "{track}"', "has no sustain pedal (drums and audio don't)",
                     plain="Pedal works on a track that plays notes.")
        starts = sorted({round(c["start"], 6) for c in cs})
        end = max(end_of(root, ctx.item(i)) for c in cs for i in c["ids"])
        pts = []
        for i, s in enumerate(starts):
            down = tempo.seconds_at(root, tempo.beat_at(root, s) + catch)
            if i + 1 < len(starts) and down >= starts[i + 1]:
                ctx.fail(codes.BAD_ARGUMENT, "catch", f"{catch:g} beats reaches the next chord at {starts[i + 1]:.2f} s",
                         hint="Use a shorter catch.", plain="The chords are closer together than the pedal's catch.")
            up, catch_at = _beat(root, s), _beat(root, down)
            pts += ([[up, 1]] if i else []) + [[up, 0], [catch_at, 0], [catch_at, 1]]   # a jump at each change, no ramp
        pts += [[_beat(root, end), 1], [_beat(root, end), 0]]
        lane = next((a for a in ctx.item(track).get("automation", []) if a.get("lane") == "sustain"), None)
        old = lane["points"] if lane else []
        keep_before = [p for p in old if times.seconds(p[0], root, "sustain") < starts[0] - 1e-6]
        keep_after = [p for p in old if times.seconds(p[0], root, "sustain") > end + 1e-6]
        new = keep_before + pts + keep_after
        if lane:
            ctx.set(lane["id"], "points", new)
        else:
            id_ = ids.lane(track, "sustain")
            if id_ in taken(ctx):
                ctx.fail(codes.BAD_ARGUMENT, f'"{id_}"', "is already used in this document")
            ctx.insert(track, "automation", {"id": id_, "type": "automation", "lane": "sustain", "points": new})
