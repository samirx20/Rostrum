"""`note.thin` / `hit.thin`: fewer notes (or drum hits) in a selection or a range, one undo step. Exactly one mode:
`keep_every` N keeps every Nth of each track's notes in time order (the first one if `offset` is 0, else the one
`offset` places in) and removes the rest; `below_vel` removes the ones played softer than that. What stayed and what went
is in the reply (the edit reply's removed list and "Kept K of the N targeted").
"""
from __future__ import annotations

from rostrum_core import Param, codes

from . import values as V
from .registry import REGISTRY
from .select_time import start_of

LABELS = {"note": "note", "hit": "drum hit"}
KEEP = Param.number("keep_every", min=2, max=64, integer=True, group="Thin", label="Keep every",
                    help="Keep every Nth one of each track, in time order (2 = every other one) and remove the others. "
                         "Give this or `below_vel`.")
OFFSET = Param.number("offset", min=0, max=63, integer=True, default=0, group="Thin", importance="secondary", label="Start at",
                      help="With keep_every: which one of each N is kept, counting from 0 (0 keeps the 1st, 3rd, 5th … for 2; "
                           "1 keeps the 2nd, 4th …). Must be less than keep_every.")
BELOW = V.N("below_vel", 0, 1, "Thin", label="Remove softer than", display="percent",
            help="Remove every one played softer than this velocity (0 … 1; a missing velocity counts as the default 0.8 for "
                 "a note, 0.85 for a hit). Give this or `keep_every`.")
DEFAULT_VEL = {"note": 0.8, "hit": 0.85}


def _thin(kind):
    @REGISTRY.operation(f"{kind}.thin", f"Fewer {LABELS[kind]}s in the target (ids, or a range: "
                        '{"track": "pad", "from": {"bar": 1}, "to": {"bar": 9}}). Exactly one mode: `keep_every` N keeps every '
                        f"Nth {LABELS[kind]} of each track in time order (`offset` picks which; 0 = the first) and removes the "
                        f"rest; `below_vel` removes the {LABELS[kind]}s softer than that. The reply lists the removed ones and "
                        "says how many of the targeted were kept. One undo step.",
                        target=kind, params=[KEEP, OFFSET, BELOW], label=f"Thin {LABELS[kind]}s")
    def thin(ctx, targets, args):
        given = [k for k in ("keep_every", "below_vel") if k in args]
        if len(given) != 1:
            ctx.fail(codes.BAD_ARGUMENT, "arguments", f"name {' and '.join(given) or 'neither keep_every nor below_vel'}: "
                     "give exactly one", ["{keep_every: 2}", "{below_vel: 0.3}"])
        if given == ["below_vel"]:
            gone = [t for t in targets if ctx.item(t).get("vel", DEFAULT_VEL[kind]) < args["below_vel"]]
        else:
            n, off = args["keep_every"], args.get("offset", 0)
            if off >= n:
                ctx.fail(codes.BAD_ARGUMENT, "offset", f"{off} is not less than keep_every {n}", hint=f"Use 0 … {n - 1}.")
            tracks: dict[str, list] = {}
            for t in dict.fromkeys(targets):
                tracks.setdefault(ctx.idx[t].parent, []).append(t)
            gone = []
            for ids in tracks.values():
                ids.sort(key=lambda t: (start_of(ctx.doc, ctx.item(t)), t))
                gone += [t for i, t in enumerate(ids) if i % n != off]
        for t in gone:
            ctx.remove(t)


for _kind in LABELS:
    _thin(_kind)
