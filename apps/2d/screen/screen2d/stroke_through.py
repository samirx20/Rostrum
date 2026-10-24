"""Picked strokes of a painted fill painted in place (Select strokes, S): the painting's strokes are shown, lassoed,
moved, scaled and turned through the element they are seen on, by the painted fill's one mapping (rostrum2d/painted.py)
and the element's place: composition px <-> the painting's px, in the tile under the lasso's middle (on Tile the
painting repeats; that tile is the one worked in). No Qt.
"""
from __future__ import annotations

import math

from rostrum2d import paint_through
from rostrum2d.evaluate import resolve
from rostrum2d.placement import comp_point, own_point


class Through:
    def __init__(self, bridge, layer: dict, painting: dict, place: dict, at: tuple[float, float] | None = None):
        t = bridge.own_t(layer["id"])
        self.place = place
        self.m = m = paint_through.mapping(layer, resolve(layer, t), painting, t, (place["w"], place["h"]))
        u, v = m.to_painting(*own_point(place, *at)) if at and m.tiled else (0.0, 0.0)
        self.dx, self.dy = math.floor((u + 0.5) / m.pw) * m.pw, math.floor((v + 0.5) / m.ph) * m.ph

    def to_comp(self, points: list) -> list:
        return [[*comp_point(self.place, *self.m.to_layer(q[0] + self.dx, q[1] + self.dy)), *q[2:]] for q in points]

    def to_canvas(self, points: list) -> list:
        out = []
        for q in points:
            u, v = self.m.to_painting(*own_point(self.place, q[0], q[1]))
            out.append([round(u - self.dx, 2), round(v - self.dy, 2), *q[2:]])
        return out
