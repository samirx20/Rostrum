"""The Clay tool's sums (clay_tool_qt.py), no Qt: the brush ring lying on the surface under the pointer, seen through the
viewport's camera, and points moved from the world into a clay's own space (the clay operations take its own space,
CL1 CONTRACT § 1). Picture px in, parts of the viewport (0..1) out, like the paint trail.
"""
from __future__ import annotations

import math

from rostrum3d import aim, through

from .gizmo import View

RING_POINTS = 40


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / n for c in v]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def clay_world(scene: dict, clay_id: str, frame: int):
    """The clay item's world transform (its own space → world)."""
    return through.find_item(scene, clay_id, frame)[0]


def to_clay(scene: dict, clay_id: str, frame: int, p) -> list[float]:
    """World point p in the clay's own space, to a tenth of a millimetre."""
    return [round(c, 4) for c in aim.point(aim.invert(clay_world(scene, clay_id, frame)), list(p))]


def world_radius(scene: dict, clay_id: str, frame: int, size: float) -> float:
    """A brush radius in the clay's own metres, in world metres (the clay's scale; the largest axis)."""
    m = clay_world(scene, clay_id, frame)[0]
    return size * max(math.sqrt(sum(m[r][c] ** 2 for r in range(3))) for c in range(3))


def ring(cam: dict, scene: dict, frame: int, point, normal, radius: float, n: int = RING_POINTS) -> list[list[float]]:
    """The circle of `radius` (world m) around `point` in the surface's plane (`normal`), as [x, y] parts of the picture;
    [] when any of it is behind the camera."""
    w, h = cam["width"], cam["height"]
    view = View.of(cam, scene, frame, w, h)
    nrm = _norm(normal)
    a = _norm(_cross(nrm, [0.0, 1.0, 0.0] if abs(nrm[1]) < 0.9 else [1.0, 0.0, 0.0]))
    b = _cross(nrm, a)
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t) * radius, math.sin(t) * radius
        q = view.project([point[k] + a[k] * c + b[k] * s for k in range(3)])
        if q is None:
            return []
        out.append([q[0] / w, q[1] / h])
    return out


def opposite(brush: str, ctrl: bool, shift: bool) -> tuple[str, bool]:
    """(the brush a stroke uses, invert): Shift = Smooth with any brush; Ctrl = the opposite: Add <-> Carve swap the brush,
    Flatten (puff out), Crease (pinch out to a ridge) and Mask (take the mask away) keep theirs with `invert`."""
    if shift:
        return "smooth", False
    if ctrl and brush in ("add", "carve"):
        return {"add": "carve", "carve": "add"}[brush], False
    return brush, ctrl and brush in INVERTS


INVERTS = ("flatten", "crease", "mask")         # the brushes whose Ctrl opposite is `invert` on the same brush


def pressure(p: float) -> float | None:
    """A pen's pressure (QML's eventPoint.pressure, 0..1) as a point's third value; None for a mouse (QML sends -1).
    Kept above 0.01: a pen just touching still makes a (tiny) dab, never one of no size."""
    return None if p < 0 else round(min(1.0, max(0.01, p)), 3)


def ring_px(ring: list, centre, w: float, h: float) -> float:
    """The ring's mean radius in px of a w x h picture (the ring's points are parts of it)."""
    if not ring or centre is None:
        return 0.0
    return sum(math.hypot((p[0] - centre[0]) * w, (p[1] - centre[1]) * h) for p in ring) / len(ring)


def sized(size0: float, ring0_px: float, dx_px: float, lo: float, hi: float) -> float:
    """F + drag: the brush size after a drag of dx_px to the right (left: smaller), so the ring's edge follows the
    pointer (its radius on screen grows by dx), within the field's range; a millimetre's tenth."""
    r0 = max(ring0_px, 8.0)
    return round(min(hi, max(lo, size0 * max(0.02, (r0 + dx_px) / r0))), 4)
