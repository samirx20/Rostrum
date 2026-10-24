"""Where a painted fill's painting sits in a layer: the ONE mapping between the layer's own px (its box, edge to edge) and
the painting's px (pixel centres, as the painting kit counts them), the engine's own layout (stage_raster.rs › raster):

- Fill / Fit: the painting scaled to cover / to sit inside the box, times Scale, centred, moved by Offset;
- Stretch: the painting is the box;
- Tile: the painting at its own size times Scale, repeated; tile 0 is the one centred on the box, the grid moved by Offset
  plus Drift × the seconds since the layer's start, turned by Rotation about the box's centre.

`to_painting` is what the screen's pen and `paint.stroke {through}` send a stroke through (painting in place, design
§ 3.3); `to_layer` goes back (look_at, the round-trip test). On Tile the painting px run on past the painting's edges
(tile 1 is x + w): `pieces` lays a stroke that crosses a tile edge once per tile it touches, each shifted into the
painting, so it carries on in the next tile under the pen.
"""
from __future__ import annotations

import math

STRETCH, TILE = "stretch", "tile"


class Mapping:
    def __init__(self, props: dict, painting: dict, box: tuple[float, float], since: float = 0.0):
        """`props`: the layer's values at that moment (resolve), `box`: its own w × h, `since`: seconds since its start."""
        self.w, self.h = float(box[0]), float(box[1])
        self.pw, self.ph = int(painting.get("w", 512)), int(painting.get("h", 512))
        self.fit = props.get("fillFit", "fill")
        s = float(props.get("fillScale", 1.0))
        if self.fit != STRETCH and not s > 0:
            raise ValueError(f"fillScale {s} must be more than 0")
        if self.w <= 0 or self.h <= 0:
            raise ValueError("the layer has no size here, so its fill has no point on it")
        pw, ph, w, h = self.pw, self.ph, self.w, self.h
        if self.fit == "fill":
            k = max(w / pw, h / ph) * s
        elif self.fit == "fit":
            k = min(w / pw, h / ph) * s
        else:
            k = s
        self.tw, self.th = (w, h) if self.fit == STRETCH else (pw * k, ph * k)
        ox, oy = (0.0, 0.0) if self.fit == STRETCH else (props.get("fillOffsetX", 0.0), props.get("fillOffsetY", 0.0))
        if self.fit == TILE:
            ox += props.get("fillDriftX", 0.0) * since
            oy += props.get("fillDriftY", 0.0) * since
            turn = math.radians(props.get("fillRotation", 0.0))
        else:
            turn = 0.0
        self.ox, self.oy, self.cos, self.sin = ox, oy, math.cos(turn), math.sin(turn)

    @property
    def tiled(self) -> bool:
        return self.fit == TILE

    def to_painting(self, lx: float, ly: float) -> tuple[float, float]:
        """A point in the layer's own px -> the painting's px (on Tile, unwrapped: past an edge is the next tile)."""
        if self.fit == TILE:        # about the box's centre, less the grid's move, turned back, from the tile's centre
            dx, dy = lx - self.w / 2 - self.ox, ly - self.h / 2 - self.oy
            u, v = dx * self.cos + dy * self.sin + self.tw / 2, -dx * self.sin + dy * self.cos + self.th / 2
        else:
            u, v = lx - (self.w - self.tw) / 2 - self.ox, ly - (self.h - self.th) / 2 - self.oy
        return u * self.pw / self.tw - 0.5, v * self.ph / self.th - 0.5

    def to_layer(self, px: float, py: float) -> tuple[float, float]:
        """The other way: painting px (any tile's) -> the layer's own px."""
        u, v = (px + 0.5) * self.tw / self.pw, (py + 0.5) * self.th / self.ph
        if self.fit != TILE:
            return u + (self.w - self.tw) / 2 + self.ox, v + (self.h - self.th) / 2 + self.oy
        a, b = u - self.tw / 2, v - self.th / 2
        return a * self.cos - b * self.sin + self.w / 2 + self.ox, a * self.sin + b * self.cos + self.h / 2 + self.oy

    def points(self, points) -> list[list[float]]:
        """[[x, y, pressure?, lean x?, lean y?], …] in layer px -> painting px, rounded to 0.01; a lean is turned with the
        tiles, so it points the same way on screen."""
        out = []
        for q in points:
            x, y = self.to_painting(q[0], q[1])
            rest = list(q[2:])
            if len(rest) >= 3 and self.fit == TILE:
                tx, ty = rest[1], rest[2]
                rest[1:3] = [round(tx * self.cos + ty * self.sin, 2), round(-tx * self.sin + ty * self.cos, 2)]
            out.append([round(x, 2), round(y, 2), *rest])
        return out

    def wrapped(self, px: float, py: float) -> tuple[float, float]:
        """A painting point folded into the painting (on Tile; elsewhere as it is)."""
        return (px % self.pw, py % self.ph) if self.fit == TILE else (px, py)

    def inside(self, px: float, py: float, reach: float = 0.0) -> bool:
        """Some of a dab of radius `reach` at painting px lands on the painting (always on Tile)."""
        return self.fit == TILE or (-reach <= px + 0.5 <= self.pw + reach and -reach <= py + 0.5 <= self.ph + reach)


def pieces(points: list, pw: int, ph: int, reach: float) -> list[list]:
    """A stroke in unwrapped painting px on a tiled fill -> one copy per tile it touches (dabs of radius `reach`), each
    shifted into the painting, the tile under its first point first. A stroke inside one tile is itself."""
    cells: dict = {}
    step = max(1.0, min(pw, ph) / 2)
    prev = None
    for q in points:
        x, y = q[0], q[1]
        n = 1 if prev is None else max(1, math.ceil(math.hypot(x - prev[0], y - prev[1]) / step))
        for i in range(1, n + 1):         # along the segment, so a long straight one crossing tiles misses none
            sx, sy = (x, y) if prev is None else (prev[0] + (x - prev[0]) * i / n, prev[1] + (y - prev[1]) * i / n)
            for kx in range(math.floor((sx - reach) / pw), math.floor((sx + reach) / pw) + 1):
                for ky in range(math.floor((sy - reach) / ph), math.floor((sy + reach) / ph) + 1):
                    cells.setdefault((kx, ky), None)
        prev = (x, y)
    return [[[round(q[0] - kx * pw, 2), round(q[1] - ky * ph, 2), *q[2:]] for q in points] for kx, ky in cells]
