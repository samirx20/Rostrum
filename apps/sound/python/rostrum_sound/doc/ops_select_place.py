"""Where the selected things live: `track.move` (the tracks' order), `track.duplicate` (a whole track, new ids),
`clip.to_track` (clips onto another track that can hold them) and `clip.cut_range` (cut a stretch
out of clips and close the gap on that track: voice editing). Each one operation over the selection, one undo step;
an agent calls the same ones the screen does (Ctrl+] / Ctrl+[, Duplicate track, ↑ ↓, Delete on a time range).
"""
from __future__ import annotations

import copy

from rostrum_core import Param, codes

from . import ids, times
from . import values as V
from .ops_group import mates
from .ops_select_clips import _new_effect_ids
from .registry import REGISTRY, taken
from .select_time import at_seconds, clip_length, length_like, moved, need_same_kind, source_length, speed, start_of

STEPS = Param.number("by", integer=True, min=-100, max=100, label="Move by", group="Order",
                     help="Places in the track list: -1 = up one, 1 = down one.")
AFTER = Param.text("after", label="After", group="Order",
                   help='Instead of `by`: the id of the track they go right under, or "top" for the very top (their order among '
                        'themselves stays).')
TRACK = Param.text("track", required=True, label="Track", group="Track",
                   help="The id of the track they go to (it must hold that kind: not a voice track for clips).")
FROM = V.time("at", required=True, group="Cut", label="From", help="Where the stretch to cut out starts.")
TO = V.time("end", required=True, group="Cut", label="To", help="Where it ends; what follows on the track moves up.")
TIMED = ("notes", "hits", "clips", "lines")


@REGISTRY.operation("track.move", "Move tracks in the track list: up or down by a number of places (by), or right under another "
                    "track (after). Their order among themselves stays.",
                    target="track", params=[STEPS, AFTER], label="Move track")
def track_move(ctx, targets, args):
    order = [t["id"] for t in ctx.doc.get("tracks", [])]
    picked = set(targets)
    if ("by" in args) == ("after" in args):
        ctx.fail(codes.BAD_ARGUMENT, "move", "needs one of by or after", ["by", "after"])
    if "after" in args:
        rest, mine = [t for t in order if t not in picked], [t for t in order if t in picked]
        anchor = args["after"]
        if anchor != "top" and anchor not in rest:
            ctx.fail(codes.BAD_ARGUMENT, f"after={anchor!r}", "is not a track the moved ones are not", ["top", *rest])
        at = 0 if anchor == "top" else rest.index(anchor) + 1
        order = rest[:at] + mine + rest[at:]
    by = int(args.get("by", 0))
    for _ in range(abs(by)):
        step = 1 if by > 0 else -1
        for i in (reversed(range(len(order))) if step > 0 else range(len(order))):
            j = i + step
            if order[i] in picked and 0 <= j < len(order) and order[j] not in picked:
                order[i], order[j] = order[j], order[i]
    for i, t in enumerate(order):
        if ctx.idx[t].index != i:
            ctx.move(t, "root", "tracks", i)


def _renamed(value, old: str, new: str):
    """Every id (and reference) under a copied track: "pad.n0" -> "pad 2.n0"."""
    if isinstance(value, dict):
        return {k: _renamed(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [_renamed(v, old, new) for v in value]
    if isinstance(value, str) and value.startswith(old + "."):
        return new + value[len(old):]
    return value


@REGISTRY.operation("track.duplicate", "Copy tracks with everything on them (notes, hits, clips, effects, lanes); "
                    "each copy sits right under its track, with new ids.", target="track", label="Duplicate track")
def track_duplicate(ctx, targets, args):
    for t in targets:
        have, src = taken(ctx), ctx.item(t)
        n = 2
        while f"{t}_{n}" in have:
            n += 1
        new = _renamed(copy.deepcopy(src), t, f"{t}_{n}")
        new["id"], new["name"] = f"{t}_{n}", f'{src.get("name") or t} {n}'
        ctx.insert("root", "tracks", new, ctx.idx[t].index + 1)


@REGISTRY.operation("clip.to_track", "Move clips onto another track (a layered clip takes its "
                    "layers along); their times stay.", target="clip", params=[TRACK],
                    label="Move to track")
def to_track(ctx, targets, args):
    dest = args["track"]
    if dest not in ctx.idx or ctx.idx[dest].item.get("type") != "track":
        ctx.fail(codes.NOT_FOUND, f'track "{dest}"', "is not a track in this song")
    if ctx.item(dest).get("instrument") == "voice":
        ctx.fail(codes.BAD_ARGUMENT, f'track "{dest}"', "is a voice track: it holds spoken lines, not clips",
                 hint="Choose an audio track.")
    every = list(dict.fromkeys(targets + [m["id"] for t in targets for m in mates(ctx, t)]))
    for t in every:
        if ctx.idx[t].parent != dest:
            ctx.move(t, dest, "clips")


@REGISTRY.operation("clip.cut_range", "Cut a stretch of time out of the selected clips (one track) and close the gap: "
                    "everything on that track after the stretch moves earlier by its length.", target="clip",
                    params=[FROM, TO], label="Cut out and close the gap", importance="secondary")
def cut_range(ctx, targets, args):
    root = ctx.doc
    a, b = sorted((times.seconds(args["at"], root, "cut"), times.seconds(args["end"], root, "cut")))
    if b - a < 1e-4:
        ctx.fail(codes.BAD_ARGUMENT, "end", "must be after the start", hint="Give a stretch, not a moment.")
    track = need_same_kind(ctx, targets, "cutting a stretch out")
    clips = [ctx.item(t) for t in targets]
    hit = [c for c in clips if start_of(root, c) < b - 1e-6 and start_of(root, c) + clip_length(c, root) > a + 1e-6]
    if not hit:
        ctx.fail(codes.BAD_ARGUMENT, "at", f"{a:.3f}–{b:.3f} s is not inside any selected clip",
                 hint="Put the stretch inside a clip.")
    later = [it for k in TIMED for it in ctx.item(track).get(k, []) if it["id"] not in {c["id"] for c in hit}
             and start_of(root, it) >= b - 1e-6]
    for it in later:
        ctx.set(it["id"], "at", moved(ctx, it, -(b - a)))
    for c in hit:
        _cut(ctx, track, c, a, b)


def _cut(ctx, track, c, a, b):
    root = ctx.doc
    s = start_of(root, c)
    e = s + clip_length(c, root)
    total, sp = source_length(c, root), speed(c)
    if b < e - 1e-6:                                     # the part after the stretch: a new clip at the cut
        right = copy.deepcopy(c)
        done = (b - s) * sp
        right.update(at=at_seconds(ctx, c, max(a, s)), **{"in": round(float(c.get("in", 0)) + done, 4)})
        right["id"] = ids.clip(track, right["at"], root, taken(ctx))
        right["length"] = length_like(c.get("length"), total - done, root, max(a, s), right)
        right["fadeIn"] = 0
        _new_effect_ids(right)
        ctx.insert(track, "clips", right, ctx.idx[c["id"]].index + 1)
    if a > s + 1e-6:                                      # the part before it stays, shorter
        ctx.set(c["id"], "length", length_like(c.get("length"), (a - s) * sp, root, s, c))
        if c.get("fadeOut"):
            ctx.set(c["id"], "fadeOut", 0)
    else:
        ctx.remove(c["id"])
