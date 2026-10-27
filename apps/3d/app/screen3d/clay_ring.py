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


_TURN = [(math.cos(2 * math.pi * i / RING_POINTS), math.sin(2 * math.pi * i / RING_POINTS)) for i in range(RING_POINTS)]


def _circle(view, point, normal, radius: float) -> list[list[float]]:
    nrm = _norm(normal)
    a = _norm(_cross(nrm, [0.0, 1.0, 0.0] if abs(nrm[1]) < 0.9 else [1.0, 0.0, 0.0]))
    b = _cross(nrm, a)
    # View.project of point + a·c + b·s, unrolled: each of its three dot products is d0 + da·c + db·s
    d = [point[k] - view.eye[k] for k in range(3)]
    dots = [(sum(d[k] * ax[k] for k in range(3)), sum(a[k] * ax[k] for k in range(3)) * radius,
             sum(b[k] * ax[k] for k in range(3)) * radius) for ax in (view.fwd, view.right, view.up)]
    (z0, za, zb), (x0, xa, xb), (y0, ya, yb) = dots
    k0, out = 0.5 / view.tan_v, []                       # (h / 2 / tan_v) / h: in parts of the picture
    aspect = view.h / view.w
    for c, s in _TURN:
        z = z0 + za * c + zb * s
        if z <= 1e-6:
            return []
        k = k0 / z
        out.append([0.5 + (x0 + xa * c + xb * s) * k * aspect, 0.5 - (y0 + ya * c + yb * s) * k])
    return out


def ring(cam: dict, scene: dict, frame: int, point, normal, radius: float) -> list[list[float]]:
    """The circle of `radius` (world m) around `point` in the surface's plane (`normal`), as [x, y] parts of the picture;
    [] when any of it is behind the camera."""
    return _circle(View.of(cam, scene, frame, cam["width"], cam["height"]), point, normal, radius)


class Ringer:
    """`ring` for the pointer's every move: the camera's view and the clay's scale are found once per scene, camera and
    size of the picture (they cost ~0.3 ms a move otherwise), only the 40 points are worked out each time."""

    def __init__(self):
        self._key, self._scene, self._view, self._scale = None, None, None, 1.0

    def ring(self, cam: dict, scene: dict, frame: int, point, normal, clay_id: str, size: float) -> list[list[float]]:
        """The ring of a brush `size` (the clay's own m) on clay `clay_id` at `point`, as `ring`."""
        key = (frame, clay_id, cam.get("camera"), tuple(cam.get("eye", ())), tuple(cam.get("target", ())),
               cam.get("fov"), cam["width"], cam["height"])
        if key != self._key or scene is not self._scene:            # (the scene kept: a new one is never a reused id)
            self._key, self._scene = key, scene
            self._view = View.of(cam, scene, frame, cam["width"], cam["height"])
            self._scale = world_radius(scene, clay_id, frame, 1.0)
        return _circle(self._view, point, normal, size * self._scale)


def inner(falloff: float) -> float:
    """Where the brush works at half strength, as a share of its radius: the ring's faint inner circle. The engine's dab
    weight (core/src/clay_band.cpp `weight`): 0 soft .. 1 hard edge."""
    h = min(1.0, max(0.0, falloff))
    if h < 0.5:
        return math.sqrt(1.0 - 0.5 ** (1.0 / (2.0 + 4.0 * (0.5 - h))))
    lo = 1.6 * (h - 0.5)
    return lo + math.sqrt(1.0 - math.sqrt(0.5)) * (1.0 - lo)


def mark(brush: str, ctrl: bool, shift: bool) -> str:
    """What the ring shows in its middle while Ctrl turns the brush to its opposite: "−" when the stroke now takes away
    (Carve, Mask's unmask), "+" when it now adds (Add, Flatten's puff out, Crease's ridge); "" otherwise."""
    return mark_of(brush, *opposite(brush, ctrl, shift))


def mark_of(chosen: str, brush: str, invert: bool) -> str:
    """`mark` for a stroke of `brush` (+ `invert`) when the chosen brush is `chosen` (Shift's Smooth: no mark)."""
    if brush == "smooth" or (brush == chosen and not invert):
        return ""
    return "−" if brush == "carve" or (brush == "mask" and invert) else "+"


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
