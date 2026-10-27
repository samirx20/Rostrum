"""The gizmo's maths (SPEC §4.1, §14): where its handles are on screen, which one the pointer is on, and what a drag
on it writes. No Qt; gizmo_qt.py puts it on screen and turns each drag into one undo step.

A View is the camera the viewport looks through (free, through a light, or the shot camera's wider copy, shot_frame.py),
projecting world points to picture pixels and pixels back to rays. Handles: move arrows along the world axes and a
square in the middle (move in the view's plane), turn rings around the world axes, scale cubes on the item's own axes.
Position is where the pivot is (compile.pivoted), so the gizmo stands on x y z. Snapping is the kit's one rule
(rostrum_gui.snap: 6 screen px, Ctrl frees).
"""
from __future__ import annotations

import math

from rostrum3d import aim, through
from rostrum_gui.snap import Target, snap

from .viewcam import _add, _cross, _norm, _sub
from .shot_frame import VIEW_CAMERA

ARM = 90.0                   # handle length, screen px
SCALE_AT = 0.62              # scale cubes sit this far along an arm
HIT = 9.0                    # how near the pointer must be to a handle, screen px
TURN_STEP = 15.0             # degrees a turn snaps to (Ctrl frees)
AXES = ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])


def columns(m) -> list[list[float]]:
    """A 3×3's axes (its columns), each made unit length."""
    return [_norm([m[r][c] for r in range(3)]) for c in range(3)]
SHOWS = {"all": ("move", "turn", "scale"), "move": ("move",), "turn": ("turn",), "scale": ("scale",)}


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


class View:
    def __init__(self, eye, right, up, forward, tan_v, w, h):
        self.eye, self.right, self.up, self.fwd, self.tan_v, self.w, self.h = eye, right, up, forward, tan_v, w, h

    @classmethod
    def of(cls, cam_request: dict, scene: dict, frame: int, w: int, h: int) -> "View":
        """From the engine request's camera part (camera, or eye + target + fov)."""
        if "camera" in cam_request:
            world, v, _ = through.find_item(scene, cam_request["camera"], frame)
            m = world[0]
            eye = aim.point(world, [0.0, 0.0, 0.0])
            right, up = _norm([m[i][0] for i in range(3)]), _norm([m[i][1] for i in range(3)])
            fwd = [-x for x in _norm([m[i][2] for i in range(3)])]
            return cls(eye, right, up, fwd, v["sensorWidth"] * h / w / 2 / v["focalLength"], w, h)
        eye, fwd = cam_request["eye"], _norm(_sub(cam_request["target"], cam_request["eye"]))
        right = _norm(_cross(fwd, [0.0, 1.0, 0.0]))
        return cls(eye, right, _cross(right, fwd), fwd, math.tan(math.radians(cam_request["fov"] / 2)), w, h)

    def project(self, p):
        """(x, y) picture px and depth of world point p; depth ≤ 0 is behind the camera."""
        d = _sub(p, self.eye)
        z = _dot(d, self.fwd)
        if z <= 1e-6:
            return None
        k = self.h / 2 / (z * self.tan_v)
        return (self.w / 2 + _dot(d, self.right) * k, self.h / 2 - _dot(d, self.up) * k, z)

    def ray(self, x, y):
        k = 2 * self.tan_v / self.h
        return _norm(_add(_add(self.fwd, self.right, (x - self.w / 2) * k), self.up, -(y - self.h / 2) * k))

    def units(self, depth) -> float:
        """World units per screen px at `depth`."""
        return 2 * depth * self.tan_v / self.h


def item_frame(carrier, values):
    """(the transform the item's own x y z live in, the gizmo's world origin, the item's own turn (3×3)). `carrier` is
    the item's seen placement (resolve.Frames.carrier): its parent's world, or that shifted by a stick and carried by a
    follow, so the gizmo stands where the item is seen and a drag edits its own offset."""
    turn = aim.local({**values, "sx": 1.0, "sy": 1.0, "sz": 1.0, "x": 0.0, "y": 0.0, "z": 0.0})[0]
    return carrier, aim.point(carrier, [values["x"], values["y"], values["z"]]), turn


def handles(view: View, origin, axes, own_axes, show="all", aimed=False, px=1.0) -> list[dict]:
    """The handles in picture px: {id, kind, axis, a, b} (lines) or {id, kind, axis, points} (rings). `axes`: the
    parent's axes in the world (where x y z and the turns live); `own_axes`: the item's own (scale). `px`: picture px
    per screen px."""
    o = view.project(origin)
    if o is None:
        return []
    arm = view.units(o[2]) * ARM * px
    out = [{"id": "plane", "kind": "move", "axis": -1, "a": o[:2], "b": o[:2]}] if "move" in SHOWS[show] else []
    for i, a in enumerate(axes):
        if "move" in SHOWS[show]:
            end = view.project(_add(origin, a, arm))
            if end:
                out.append({"id": f"move{i}", "kind": "move", "axis": i, "a": o[:2], "b": end[:2]})
        if "turn" in SHOWS[show] and not aimed:
            pts = _ring(view, origin, axes[(i + 1) % 3], axes[(i + 2) % 3], arm * 0.8)
            if pts:
                out.append({"id": f"turn{i}", "kind": "turn", "axis": i, "points": pts})
        if "scale" in SHOWS[show]:
            end = view.project(_add(origin, own_axes[i], arm * SCALE_AT))
            if end:
                out.append({"id": f"scale{i}", "kind": "scale", "axis": i, "a": o[:2], "b": end[:2]})
    return out


_CIRCLE = [(math.cos(2 * math.pi * k / 48), math.sin(2 * math.pi * k / 48)) for k in range(49)]


def _ring(view: View, origin, u, v, r):
    """A turn ring's 49 points in picture px (None if part of it is behind the camera): View.project of origin +
    r·(u cos t + v sin t), worked out from nine dot products (a scrub step redraws the rings: ~1.5 ms point by point)."""
    c = _sub(origin, view.eye)
    cz, uz, vz = _dot(c, view.fwd), r * _dot(u, view.fwd), r * _dot(v, view.fwd)
    cx, ux, vx = _dot(c, view.right), r * _dot(u, view.right), r * _dot(v, view.right)
    cy, uy, vy = _dot(c, view.up), r * _dot(u, view.up), r * _dot(v, view.up)
    hw, hh, s = view.w / 2, view.h / 2, view.h / 2 / view.tan_v
    out = []
    for co, si in _CIRCLE:
        z = cz + uz * co + vz * si
        if z <= 1e-6:
            return None
        k = s / z
        out.append((hw + (cx + ux * co + vx * si) * k, hh - (cy + uy * co + vy * si) * k))
    return out


def _seg_dist(p, a, b):
    ab, ap = _sub(b, a), _sub(p, a)
    t = max(0.0, min(1.0, _dot(ap, ab) / (_dot(ab, ab) or 1e-9)))
    return math.hypot(*_sub(p, _add(a, ab, t)))


def hit(hs: list[dict], x, y, px=1.0) -> str:
    """The handle under picture point (x, y): the nearest within HIT screen px, ends and the middle first."""
    best, p = None, [x, y]
    for h in hs:
        if h["kind"] == "turn":
            d = min(_seg_dist(p, a, b) for a, b in zip(h["points"], h["points"][1:]))
        elif h["id"] == "plane":
            d = max(abs(x - h["a"][0]), abs(y - h["a"][1])) - 5 * px
        elif h["kind"] == "scale":
            d = math.hypot(x - h["b"][0], y - h["b"][1]) - 3 * px
        else:
            d = _seg_dist(p, h["a"], h["b"]) - (2 * px if math.hypot(x - h["b"][0], y - h["b"][1]) < 12 * px else 0)
        if d <= HIT * px and (best is None or d < best[0]):
            best = (d, h["id"])
    return best[1] if best else ""


def _closest_on_axis(view, x, y, origin, a) -> float:
    """How far along the line origin + s·a the pointer's ray passes nearest."""
    d, w0 = view.ray(x, y), _sub(origin, view.eye)
    b, dd, e = _dot(a, d), _dot(d, d), _dot(a, w0)
    den = _dot(a, a) * dd - b * b
    return 0.0 if abs(den) < 1e-9 else (b * _dot(d, w0) - dd * e) / den


def _on_plane(view, x, y, origin):
    d = view.ray(x, y)
    s = _dot(_sub(origin, view.eye), view.fwd) / (_dot(d, view.fwd) or 1e-9)
    return _add(view.eye, d, s)


def moved_by(view, handle, origin, axes, start, now) -> list[float]:
    """World displacement of a move handle dragged from picture point `start` to `now`."""
    if handle == "plane":
        return _sub(_on_plane(view, *now, origin), _on_plane(view, *start, origin))
    a = axes[int(handle[-1])]
    s = _closest_on_axis(view, *now, origin, a) - _closest_on_axis(view, *start, origin, a)
    return [s * x for x in a]


def turned_by(view, handle, origin, axes, start, now) -> float:
    """Degrees around the handle's world axis (counter-clockwise looking down the axis towards its origin)."""
    o = view.project(origin)
    ang = [math.atan2(-(p[1] - o[1]), p[0] - o[0]) for p in (start, now)]
    deg = math.degrees((ang[1] - ang[0] + math.pi) % (2 * math.pi) - math.pi)
    return deg if _dot(axes[int(handle[-1])], view.fwd) < 0 else -deg


def scaled_by(handle_line, start, now) -> float:
    """The factor a scale cube dragged from `start` to `now` scales by, along its arm on screen."""
    a, b = handle_line
    arm = _sub(b, a)
    n = _dot(arm, arm) or 1e-9
    return max(0.01, 1.0 + _dot(_sub(now, start), arm) / n)


def snapped(value, targets, px_per_unit, free) -> tuple[float, str]:
    caught = snap(value, targets, px_per_unit, free=free)
    return caught.value, caught.name


def angle_targets(value) -> list[Target]:
    base = round(value / TURN_STEP) * TURN_STEP
    return [Target("measure", f"{base + k * TURN_STEP:g}°", base + k * TURN_STEP) for k in (-1, 0, 1)]


def turn_matrix(a, deg):
    """A turn of `deg` around the unit axis `a`."""
    c, s, t = math.cos(math.radians(deg)), math.sin(math.radians(deg)), 1 - math.cos(math.radians(deg))
    x, y, z = a
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]


__all__ = ["View", "VIEW_CAMERA", "handles", "hit", "item_frame", "moved_by", "turned_by", "scaled_by", "snapped",
           "angle_targets", "turn_matrix"]
