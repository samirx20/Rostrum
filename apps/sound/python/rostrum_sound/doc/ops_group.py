"""Layered sounds: clips and designed sounds of one track that share a `group` name are one sound made of several
takes (a designed click + a library thud).

`clip.set` on a grouped clip carries the whole group: a new `at` moves every clip of the group by the same time
(each keeps the way its own time is written), a new `volume` scales them all by the same factor. One call = one
undo step. `clip.set_one` takes the same fields but changes only the one clip (balancing a layer inside its group).
The group is just a name on each clip, so there is no second list that could disagree with the clips.
"""
from __future__ import annotations

from rostrum_core.tree import index

from . import fields as FD
from . import shift, times
from .registry import LISTS, REGISTRY, set_fields

VOLUME_MAX = 4.0


def mates(ctx, clip_id: str) -> list[dict]:
    """The other members of this clip's or sound's group (same track, same `group`: clips and designed sounds); none
    when it has no group."""
    loc = index(ctx.doc, LISTS)[clip_id]
    group = loc.item.get("group")
    if not group:
        return []
    track = ctx.item(loc.parent)
    return [c for key in ("clips", "sounds") for c in track.get(key, []) if c.get("group") == group and c["id"] != clip_id]


def clip_set(ctx, targets, args):
    """The clip's fields; its group's other clips follow a move in time and a change of level."""
    seen = set(targets)
    for t in targets:
        clip, rest = ctx.item(t), dict(args)
        group = [c for c in mates(ctx, t) if c["id"] not in seen]
        seen |= {c["id"] for c in group}
        if group and "at" in rest:
            _move(ctx, [clip, *group], clip, rest.pop("at"))
        if group and "volume" in rest and clip.get("volume", 1) > 0:
            ratio = rest["volume"] / clip.get("volume", 1)
            for c in group:
                ctx.set(c["id"], "volume", round(min(VOLUME_MAX, c.get("volume", 1) * ratio), 4))
        set_fields(ctx, [t], rest)


def _move(ctx, clips, lead, new_at):
    """Move `clips` by the time `lead` moves to `new_at`; the group stops at the start of the mix."""
    root = ctx.doc
    now = {c["id"]: times.seconds(c["at"], root, c["id"]) for c in clips}
    asked = times.seconds(new_at, root, lead["id"]) - now[lead["id"]]
    delta = max(asked, -min(now.values()))
    for c in clips:
        ctx.set(c["id"], "at", new_at if c is lead and delta == asked
                else shift.write_like(c["at"], now[c["id"]] + delta, root))


REGISTRY.operation("clip.set_one", "Change one clip only, even when it is layered in a group (clip.set moves or "
                   "re-levels the whole group).", target="clip", params=FD.params("clip"), label="Edit one clip",
                   importance="secondary")(set_fields)
