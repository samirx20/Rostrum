"""`paint.stroke` on a painting `through` a layer filled with it (painting in place, design § 3.3): the points go through
that layer's Fit, Scale, Offset, Rotation and Drift at `frame` (painted.Mapping, the engine's layout) into the painting's
px, into the drawing that layer shows then. On Tile a stroke that crosses a tile edge carries on in the next tile
(painted.pieces: one copy per tile it touches, all in the one change); on a seamless painting it is one stroke that the
painting kit wraps (wrap.py: any use, Tile or not, and never laid twice where the copies would meet). Paint that would land wholly outside the painting
(the empty bands Fit leaves) is refused, loudly. The screen's pen sends the points it already took through the same
Mapping (space "canvas"), so a person's stroke and an agent's land alike.
"""
from __future__ import annotations

import math

import rostrum_paint
from rostrum_core.errors import codes

from . import painted, painted_fill, paint_grow, paintings, placement
from .evaluate import resolve
from .names import display_name
from .sizes import own_size


def mapping(layer: dict, props: dict, painting: dict, t: float, box=None) -> painted.Mapping:
    """The layer's mapping at its own time `t` (box: its own size there unless given, e.g. the engine's place)."""
    return painted.Mapping(props, painting, box or own_size(layer["type"], props), t - layer.get("start", 0.0))


def stroke(ctx, painting_id: str, args: dict, brush: dict, fps: float, place) -> tuple[int, list[list]]:
    """(the painting's frame the stroke goes in, the stroke's point lists in painting px: one, or one per tile)."""
    lid, painting = args["through"], ctx.item(painting_id)
    layer = ctx.item(lid)
    if layer.get("fillType") != "painted" or layer.get("fillPainting") != painting_id:
        ctx.fail(codes.BAD_ARGUMENT, f'through "{lid}"', f'has no painted fill of "{painting.get("name", painting_id)}"',
                 hint="Pass a layer whose fill is this painting (inspect_painting lists its uses).")
    n = args.get("frame", 0)
    props = resolve(layer, n / fps)
    space, pts = args.get("space", "comp"), args["points"]
    try:
        if space == "comp":         # where the engine draws the layer at that frame, its own px, then into the painting
            p = place(ctx, lid, n)
            m = mapping(layer, props, painting, n / fps, (p["w"], p["h"]))
            pts = m.points([[*placement.own_point(p, q[0], q[1]), *q[2:]] for q in pts])
        else:
            m = mapping(layer, props, painting, n / fps)
            if space == "layer":
                pts = m.points(pts)
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, f'"{lid}" at frame {n}', str(e))
    x0, _, x1, _ = paint_grow.reach(pts[:1], {**rostrum_paint.brush_defaults(), **brush})
    r = (x1 - x0) / 2
    if not any(m.inside(q[0], q[1], r) for q in pts):
        bands = " (Fit leaves the bands empty)" if m.fit == "fit" else ""
        ctx.fail(codes.BAD_ARGUMENT, "points", f'are outside the painting "{painting.get("name")}" in {display_name(layer)}{bands}',
                 hint="Paint over the painting itself.",
                 plain=f'{display_name(layer)}: the stroke is outside the painting {painting.get("name")}{bands}.')
    shown = painted_fill.shown(layer, painting, n, fps)
    if paintings.seamless(painting):     # the kit wraps it (wrap.py): one stroke, moved into the tile under its start
        kx, ky = math.floor((pts[0][0] + 0.5) / m.pw), math.floor((pts[0][1] + 0.5) / m.ph)
        return (shown["at"] if shown else 0), [[[round(q[0] - kx * m.pw, 2), round(q[1] - ky * m.ph, 2), *q[2:]] for q in pts]]
    return (shown["at"] if shown else 0), painted.pieces(pts, m.pw, m.ph, r) if m.tiled else [pts]
