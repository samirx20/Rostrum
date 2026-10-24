"""Paintings of a scene (design: C:\\Users\\Sam\\.rostrum\\waves\\results\\2d-painted-fill\\DESIGN.md): a painting is an item of
the document's `paintings` list that holds the painting kit's canvas exactly as a drawing does (`frames`, drawing.py), plus
its own w × h and Seamless. Shapes and paths fill themselves with one (`fillType` "painted", `fillPainting` its id): editing
it changes every layer using it, in one history. This module reads: who uses a painting, a painting's average colour (what
a deleted painting's uses turn into) and the document check. ops_painting.py changes.
"""
from __future__ import annotations

import numpy as np
from rostrum_core.tree import walk
from rostrum_paint import canvas

from . import drawing as D
from .fill_fields import OWNERS


def all_of(doc: dict) -> list[dict]:
    return doc.get("paintings", [])


def uses(doc: dict, painting_id: str, lists: dict | None = None) -> list[dict]:
    """The layers filled with this painting, in document order."""
    from .kind import LISTS
    return [i for i in walk(doc, lists or LISTS) if i.get("fillType") == "painted" and i.get("fillPainting") == painting_id]


def average(painting: dict) -> tuple[str, float]:
    """(colour "#rrggbb", cover 0..1): the mean colour of the painting's first drawing weighted by its paint's opacity,
    and how much of the painting is covered. An empty painting is (black, 0)."""
    frames = painting.get("frames", [])
    if not frames:
        return "#000000", 0.0
    w, h = D.canvas_size(painting)
    px = canvas.rgba8(frames[0], w, h).astype(np.float64)
    alpha = px[..., 3] / 255.0
    cover = float(alpha.mean())
    if cover <= 0:
        return "#000000", 0.0
    rgb = (px[..., :3] * alpha[..., None]).sum(axis=(0, 1)) / alpha.sum()
    return "#%02x%02x%02x" % tuple(int(round(c)) for c in rgb), round(cover, 4)


def problems(data: dict, items=None) -> list[str]:
    """A painted fill names a painting that exists, and sits on a shape or a path (a text takes none yet). A change set
    (`items`) checks only the layers in it, and every layer when a painting is in it (one may have gone)."""
    from .kind import LISTS
    have = {p["id"] for p in all_of(data)}
    changed = None if items is None else {i["id"] for i in items}
    painting_changed = items is not None and any(i.get("type") == "painting" for i in items)
    out = []
    for item in walk(data, LISTS):
        if item.get("fillType") != "painted" or (changed is not None and item["id"] not in changed and not painting_changed):
            continue
        if item["type"] not in OWNERS or item["type"] == "text":
            out.append(f'{item["id"]}: a {item["type"]} takes no painted fill yet (shapes and paths do)')
        elif item.get("fillPainting") not in have:
            name = item.get("fillPainting") or "(none)"
            out.append(f'{item["id"]}.fillPainting: no painting "{name}" in this document'
                       + (f' (it has: {", ".join(sorted(have))})' if have else " (it has none: make one with painting.add)"))
    return out
