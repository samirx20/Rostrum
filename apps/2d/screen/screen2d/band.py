"""The rubber band on the canvas (CANVAS.md §2 row 25): which layers a box dragged on empty canvas picks, and, while it
grows, the outlines of those layers so they light up live (not only on release). One rule for both: the kit's
selection_rules.box (INTERACTION 1.3) over the layers the box touches, as their outermost group (never a locked one);
"shift" adds them to the selection, "ctrl" picks the deepest pieces instead. No Qt.

    touched(boxes, rect) -> [(outermost, id)]     the unlocked layers the box (x0, y0, x1, y1) touches, topmost first
    picks(b, picked, rect, mods) -> [ids]         what letting go now picks (Multi.boxSelect)
    preview(b, picked, rect, mods, was) -> (ids, path)    the same, with its outlines as one svg path; `was` itself
                                                  when nothing changed (a move that lights no other layer redraws nothing)
    outline(box) -> svg                           one turned box's outline (Multi.outlinePath draws picked layers so)

Boxes are bounds.boxes (kept per composition and time): a move costs the touch test over them (~1 ms at 200 layers),
never a picture.
"""
from __future__ import annotations

import math

from rostrum_gui.selection_rules import box

from . import bounds


def touched(boxes, rect) -> list[tuple[str, str]]:
    lo_x, hi_x = min(rect[0], rect[2]), max(rect[0], rect[2])
    lo_y, hi_y = min(rect[1], rect[3]), max(rect[1], rect[3])
    found = [x for x in boxes if not x["locked"] and x["type"] != "group"
             and (e := bounds.extent(x)) and e[0] <= hi_x and e[2] >= lo_x and e[1] <= hi_y and e[3] >= lo_y]
    return [((x["up"] or (x["id"],))[0], x["id"]) for x in reversed(found)]


def picks(b, picked, rect, mods) -> list[str]:
    return box(picked, touched(bounds.boxes(b.placed(), b._t), rect), set(mods.split()), "canvas")


def outline(x: dict) -> str:
    """The box's four corners turned about its anchor, as an svg sub-path (composition px)."""
    l, t, w, h = x["x"], x["y"], x["w"], x["h"]
    ax, ay, a = l + x.get("ax", 0) * w, t + x.get("ay", 0) * h, math.radians(x.get("rot", 0))
    c, s = math.cos(a), math.sin(a)
    pts = [(ax + (px - ax) * c - (py - ay) * s, ay + (px - ax) * s + (py - ay) * c)
           for px, py in ((l, t), (l + w, t), (l + w, t + h), (l, t + h))]
    return "M" + " L".join(f"{px:.2f},{py:.2f}" for px, py in pts) + " Z"


def preview(b, picked, rect, mods, was):
    ids = tuple(picks(b, picked, rect, mods))
    if ids == was[0]:
        return was
    return ids, " ".join(outline(x) for x in b.shown_boxes(list(ids)) if x.get("w") is not None)
