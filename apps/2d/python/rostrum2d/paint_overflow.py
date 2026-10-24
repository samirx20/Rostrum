"""A stroke a drawing can't hold (it would grow past paint_grow.MOST px a side) starts a new drawing beside it, in the
same change as the stroke (one undo step): never a lost stroke, never a silent crop (2D camera spec § 4.11.3).

The new drawing is the old one's twin in where it sits: the same parent (just above it), depth, pinned state, timing,
position, scale, turn and their keys, so its own px land exactly where the old drawing's would. Only its canvas differs:
sized to the stroke (in paint_grow.STEP chunks, growing like any drawing), its anchor moved so the same point stays put.
Named after the old one ("sky" -> "sky 2", "sky 3" …). The screen says so with `note`.
"""
from __future__ import annotations

import math
import re

from rostrum_core.errors import codes
from rostrum_core.tree import bare

from . import paint_grow as G
from .names import display_name, unique_name

COPIED = ("keys", "exprs")       # what animates where the layer sits; its paint, masks and effects stay with the old one


def start(ctx, t: str, box, points) -> tuple[str, list]:
    """(the new drawing's id, the stroke's points in its canvas px): the new drawing beside `t` holding `box`."""
    item, loc = ctx.item(t), ctx.idx[t]
    x0, y0 = math.floor(box[0]), math.floor(box[1])
    sw, sh = math.ceil(box[2]) - x0, math.ceil(box[3]) - y0
    if sw > G.MOST or sh > G.MOST:
        ctx.fail(codes.BAD_ARGUMENT, "the stroke", f"reaches {sw} × {sh} canvas px; a drawing holds {G.MOST} px a side at most",
                 hint="Paint it in shorter strokes.",
                 plain=f"This stroke is bigger than a drawing can be ({G.MOST} px a side). Paint it in shorter strokes.")
    nw, nh = (min(G.MOST, max(G.STEP, math.ceil(n / G.STEP) * G.STEP)) for n in (sw, sh))
    ox, oy = x0 - (nw - sw) // 2, y0 - (nh - sh) // 2            # the new canvas's (0, 0) in the old canvas's px
    w, h = int(item.get("w", 1920)), int(item.get("h", 1080))
    lists = ctx.kind.lists
    new = {**bare(item, lists), "id": ctx.new_id("drawing"), "name": _name(ctx, item), "w": nw, "h": nh}
    ctx.insert(loc.parent, loc.key, new, loc.index + 1)
    for key in COPIED:
        for child in item.get(key, []):
            ctx.insert(new["id"], key, {**bare(child, lists), "id": ctx.new_id(child["type"])})
    G.set_anchor(ctx, new["id"], "anchorX", lambda a: (a * w - ox) / nw)
    G.set_anchor(ctx, new["id"], "anchorY", lambda a: (a * h - oy) / nh)
    return new["id"], G.shifted(points, -ox, -oy)


def _name(ctx, item: dict) -> str:
    from rostrum_core.tree import index
    base = re.sub(r" \d+$", "", display_name(item)) or display_name(item)
    taken = {display_name(i.item) for i in index(ctx.doc, ctx.kind.lists).values() if i.item.get("type") != "doc"}
    return unique_name(taken | {item.get("name", "")}, base)


def note(change, doc) -> str | None:
    """The status line's sentence when a paint change started a new drawing ("'sky' is at its largest; this stroke
    started 'sky 2'"), else None (a drawing made for the stroke, by the pen's first stroke, is not one). `doc`: the
    document after the change (anything with `item(id)`)."""
    from rostrum_core import edits as E
    targets = [t for c in getattr(change, "calls", []) or [] if c.get("op") == "paint.stroke" for t in c.get("target", [])]
    made = [e.item for e in getattr(change, "edits", []) or []
            if isinstance(e, E.Insert) and e.key == "layers" and e.item.get("type") == "drawing" and e.id not in targets]
    if not targets or not made:
        return None
    try:
        old = doc.item(targets[0])
    except Exception:  # noqa: BLE001  the old drawing is gone since: say the new one alone
        old = None
    new = display_name(made[0])
    return f"'{display_name(old)}' is at its largest; this stroke started '{new}'" if old else f"This stroke started '{new}'"
