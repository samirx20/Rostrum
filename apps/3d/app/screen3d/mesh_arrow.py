"""The arrow Edit mesh draws for the last action's main number (SPEC 4.3), dragged to change it live: Extrude's
distance along the picked faces' normal, Bevel's width along the screen. No Qt. Picture px; the number in metres.
"""
from __future__ import annotations

import math

from .mesh_edit import centre, normal

ARROW = 70.0                 # the arrow's length, screen px


def arrow(geo, sel, px=1.0, distance=0.0):
    """The extrude arrow in picture px: (base, tip, world units per screen px along it), from the selection's centre
    along its normal; `distance` (m) moves its base with the drag."""
    c, n = centre(geo, "faces", sel), normal(geo, sel)
    base = [c[i] + n[i] * distance for i in range(3)]
    b = geo.view.project(base)
    if b is None:
        return None
    units = geo.view.units(b[2]) * px
    tip = geo.view.project([base[i] + n[i] * units * ARROW for i in range(3)])
    return (b[:2], tip[:2], units) if tip else None


def along(base, tip, units, start, now) -> float:
    """Metres the pointer moved along the arrow from `start` to `now` (picture px)."""
    ax, ay = tip[0] - base[0], tip[1] - base[1]
    n = math.hypot(ax, ay) or 1e-9
    return ((now[0] - start[0]) * ax + (now[1] - start[1]) * ay) / n * (ARROW * units / n)


def side_arrow(geo, at, px=1.0):
    """Bevel's grip: from where the bevelled edges were (`at`, world) to the right on the picture, (base, tip, world
    units per px). The edges themselves are gone once bevelled, so the action keeps their centre."""
    b = geo.view.project(at)
    if b is None:
        return None
    return (b[:2], [b[0] + ARROW * px, b[1]], geo.view.units(b[2]) * px)
