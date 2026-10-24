"""Wet ink on every layer using a painting (design 2d-painted-fill § 3.3, § 8): a stroke painted in place through one
element is stamped once, in the painting's own px (wet.py), and that one picture is laid on every use shown, through
each use's place (the engine's, paint_edge.places) and its painted fill's mapping (rostrum2d/painted.py): the stroke
shows on all of them as it is drawn and is already there at release, while the painting's picture is made and every
use swaps to it with the frame. On Tile a use shows it once per tile it has; a seamless painting that isn't tiled shows
the stroke's wrapped copies inside the painting. No Qt.
"""
from __future__ import annotations

import math

from rostrum2d import paint_through, paintings
from rostrum2d.evaluate import resolve
from rostrum2d.painted import TILE

MOST_TILES = 64                 # tiles of one use shown with wet ink (the rest show the stroke when it lands)


def _affine(f) -> list[float]:
    """[a, b, c, d, e, f]: x' = a x + c y + e, y' = b x + d y + f, from a point map `f` (affine: three points)."""
    o, x, y = f(0.0, 0.0), f(1.0, 0.0), f(0.0, 1.0)
    return [x[0] - o[0], x[1] - o[1], y[0] - o[0], y[1] - o[1], o[0], o[1]]


def start_tile(stroke) -> tuple[int, int]:
    """The tile under the stroke's first point (its painting px are unwrapped on Tile): the ink is drawn in it."""
    m = stroke._map
    return math.floor((stroke.points[0][0] + 0.5) / m.pw), math.floor((stroke.points[0][1] + 0.5) / m.ph)


def uses(bridge, painting: dict, ids: list[str]) -> list[dict]:
    """[{own, w, h, pw, ph, inner, offsets, clip}] for each use with a place: `own` its own px -> composition px, `inner` the
    painting's px -> its own px, `offsets` where the ink shows again (painting px), `clip` keep it inside the painting."""
    places, seamless, out = dict(bridge._paint_edge.places), paintings.seamless(painting), []
    missing = [i for i in ids if i not in places]
    if missing and bridge._scene:               # not drawn since they were asked for: one ask of the canvas's engine
        places.update(bridge.frames.place(bridge._scene, bridge.time, missing, world=not bridge.play.playing))
    pw, ph = painting.get("w", 512), painting.get("h", 512)
    for lid in ids:
        place = places.get(lid)
        if place is None or not bridge.doc.has(lid):
            continue
        layer = bridge.doc.item(lid)
        t = bridge.own_t(lid)
        try:
            m = paint_through.mapping(layer, resolve(layer, t), painting, t, (place["w"], place["h"]))
        except ValueError:
            continue
        a = place["m"]
        own = [a[0] / a[8], a[3] / a[8], a[1] / a[8], a[4] / a[8], a[2] / a[8], a[5] / a[8]]
        inner = _affine(lambda x, y: m.to_layer(x - 0.5, y - 0.5))
        if m.fit == TILE:
            us = [m.to_painting(x, y) for x, y in ((0, 0), (m.w, 0), (0, m.h), (m.w, m.h))]
            kx = range(math.floor(min(u for u, _ in us) / pw), math.floor(max(u for u, _ in us) / pw) + 1)
            ky = range(math.floor(min(v for _, v in us) / ph), math.floor(max(v for _, v in us) / ph) + 1)
            offsets = [[i * pw, j * ph] for i in kx for j in ky][:MOST_TILES]
            out.append({"own": own, "w": m.w, "h": m.h, "pw": pw, "ph": ph, "inner": inner, "offsets": offsets, "clip": False})
        else:
            offsets = [[i * pw, j * ph] for i in (-1, 0, 1) for j in (-1, 0, 1)] if seamless else [[0, 0]]
            out.append({"own": own, "w": m.w, "h": m.h, "pw": pw, "ph": ph, "inner": inner, "offsets": offsets, "clip": True})
    return out
