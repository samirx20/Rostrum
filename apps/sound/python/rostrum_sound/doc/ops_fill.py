"""`hit.fill`: fill a stretch of a drum track with one drum on an even spacing (every step, every beat, off-beats …),
the screen's Fill ▸ on a drum row. It adds hits only where that drum has none yet (within 10 ms), so a person's hits are
never doubled or moved, and the whole fill is one undo step. The spacing is `writing/drums.py` › `spaced`, the same
step rule the script's drum grids use. Clear is `hit.remove` on the drum's hits.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import codes

from .. import names
from ..writing.drums import spaced
from . import fields as FD
from . import ids, tempo, times
from . import values as V
from .playing import IS
from .registry import REGISTRY, taken
from .select_time import start_of

N = V.N
SAME = 0.010                                         # seconds: a hit this close to a step is that step's
KIT = {"any": [IS("instrument", "kit"), IS("instrument", "kitSfz")]}
DRUM = V.drum("drum", required=True, group="Fill", label="Drum", help='The drum to fill with ("hat", "snare", "kick" …): one '
              "the track's kit plays.")
EVERY = N("every", 1 / 32, 32, "Fill", "", default=0.25, label="Every (beats)", help="The spacing in beats: 0.25 = every 16th, "
          "0.5 = every 8th, 1 = every beat, 4 = once a bar (in 4/4), up to 32.")
OFFSET = N("offset", 0, 16, "Fill", "", default=0, label="Starting on (beats)", help="How many beats after `from` the first "
           "hit lands (0.5 with every 1 = the off-beats).")
FROM = V.time("from", required=True, group="Fill", label="From", help="Where the fill starts (a bar's start, for a bar).")
TO = V.time("to", required=True, group="Fill", label="To", help="Where it stops: no hit is placed on or after it.")
EVERY, OFFSET = (dataclasses.replace(p, step=1 / 32) for p in (EVERY, OFFSET))      # steps the screen's boxes show whole (0.25, not 0)
VEL = N("vel", 0, 1, "Fill", default=0.85, label="Velocity", display="percent", help="How hard each hit plays. Left out = 0.85.")
ACCENT_EVERY = N("accentEvery", 0, 64, "Fill", "", imp="secondary", default=0, label="Accent every (beats)",
                 help="Every this many beats from `from`, the hit is an accent (counted from the start). 0 or left out = none.")
ACCENT_VEL = N("accentVel", 0, 1, "Fill", imp="secondary", default=1, label="Accent velocity", display="percent",
               help="How hard an accent plays. Left out = 1.")


def _written_in_seconds(track: dict) -> bool:
    first = next(iter(track.get("hits", [])), None)
    return first is not None and isinstance(first["at"], (int, float))


@REGISTRY.operation("hit.fill", "Fill a stretch of a drum track with one drum on an even spacing: `every` beats from `from` "
                    "up to `to`, the first `offset` beats in, each at `vel` (every `accentEvery` beats an accent at "
                    "`accentVel`). Steps where that drum already has a hit (within 10 ms) are left as they are, so it never "
                    "doubles one. Clear a drum with hit.remove.", target="track",
                    params=[DRUM, EVERY, OFFSET, FROM, TO, VEL, ACCENT_EVERY, ACCENT_VEL], label="Fill a drum row",
                    valid_when=KIT, importance="secondary")
def fill(ctx, targets, args):
    root, drum = ctx.doc, args["drum"]
    a, b = (times.seconds(args[k], root, "fill") for k in ("from", "to"))
    if b - a < 1e-4:
        ctx.fail(codes.BAD_ARGUMENT, "to", "must be after from", hint="Give a stretch, not a moment.")
    for t in targets:
        track = ctx.item(t)
        if track.get("instrument") == "kit" and drum not in names.kit_drums(track.get("kit")) \
                and not any(h["drum"] == drum for h in track.get("hits", [])):
            ctx.fail(codes.BAD_ARGUMENT, f'drum "{drum}"', f'is not a drum the "{track.get("kit", "drums")}" kit plays',
                     hint="Choose from: " + ", ".join(names.kit_drums(track.get("kit"))))
        have = [start_of(root, h) for h in track.get("hits", []) if h["drum"] == drum]
        secs = _written_in_seconds(track)
        first, last = tempo.beat_at(root, a), tempo.beat_at(root, b)
        for beat, accent in spaced(args.get("every", 0.25), first, last, args.get("offset", 0), args.get("accentEvery")):
            sec = tempo.seconds_at(root, beat)
            if any(abs(sec - h) <= SAME for h in have):
                continue
            at = round(sec, 4) if secs else {"beat": round(beat, 4)}
            vel = args.get("accentVel", 1) if accent else args.get("vel", 0.85)
            ctx.insert(t, "hits", {"id": ids.hit(t, drum, at, root, taken(ctx), ctx.where), "type": "hit", **FD.DEFAULTS["hit"],
                                   "drum": drum, "at": at, "vel": vel})
