"""The viewport's camera (screen state, never a document value). Two modes:

- "shot": look through the shot's own camera (the request names it: `camera`).
- "free": a turntable camera, `eye` looking at `target` with a vertical `fov`, Y up (ENGINE_CONTRACT.md § 4).
  Left drag orbits around the target, or around a pivot (the viewport's: what is selected, else what is in the scene)
  so that the pivot stays where it is in the picture; pan slides both, zoom moves the eye along its line.
- "light": through a light (rostrum3d.through), from where it stands along the way it shines, following it as it moves.

`home` starts the free camera where the shot camera stands and looks, from the compiled scene (its world transform
at the frame, animated values taken from `anim`), orbiting the camera's focus point. No Qt.
"""
from __future__ import annotations

import math

from rostrum3d import aim, through

ORBIT_DEG = 0.3              # degrees per mouse pixel
ZOOM_STEP = 0.88             # distance factor per wheel step
DEFAULT = {"eye": [0.6, 0.45, 0.9], "target": [0.0, 0.0, 0.0], "fov": 35.0}


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _add(a, b, k=1.0):
    return [x + k * y for x, y in zip(a, b)]


def _norm(v):
    n = math.hypot(*v)
    return [x / n for x in v] if n > 1e-12 else [0.0, 0.0, 1.0]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _rotate(v, axis, deg):
    """v turned `deg` degrees about the unit `axis` (Rodrigues)."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    k, kv = _cross(axis, v), sum(a * b for a, b in zip(axis, v))
    return [v[i] * c + k[i] * s + axis[i] * kv * (1 - c) for i in range(3)]


def find_camera(scene: dict, camera: str, frame: int):
    """(world transform, props at `frame`) of the scene item `camera`; ValueError when it is not there."""
    try:
        world, v, node = through.find_item(scene, camera, frame)
    except ValueError:
        raise ValueError(f'viewport: no camera "{camera}" in the scene') from None
    if node["type"] != "camera":
        raise ValueError(f'viewport: "{camera}" is a {node["type"]}, not a camera')
    return world, v


class ViewCam:
    def __init__(self):
        self.mode, self.camera = "free", ""          # camera: the shot camera's id ("" = no shot)
        self.light = ""                              # the light looked through in "light" mode
        self.eye, self.target, self.fov = list(DEFAULT["eye"]), list(DEFAULT["target"]), DEFAULT["fov"]

    # --- the shot camera
    def home(self, scene: dict, camera: str, frame: int, aspect: float):
        """Free camera from the shot camera's position and aim; `aspect` = viewport width / height."""
        world, v = find_camera(scene, camera, frame)
        self.camera = camera
        self.eye = aim.point(world, [0.0, 0.0, 0.0])
        forward = _norm(_sub(aim.point(world, [0.0, 0.0, -1.0]), self.eye))     # cameras look along their −Z
        along = -sum(e * f for e, f in zip(self.eye, forward))                  # nearest the world origin on the line
        dist = v["focusDistance"] if v.get("dof") and v["focusDistance"] > 0 else along if along > 1e-3 else 1.0
        self.target = _add(self.eye, forward, dist)
        sensor_h = v["sensorWidth"] / max(aspect, 1e-6)                        # the height follows the picture
        self.fov = math.degrees(2 * math.atan(sensor_h / (2 * v["focalLength"])))
        self.mode = "free"

    # --- through a light
    def look_through(self, scene: dict, light: str, frame: int):
        self.light = light
        self.follow(scene, frame)
        self.mode = "light"

    def follow(self, scene: dict, frame: int):
        """Stand where the light is at `frame` (it may have moved since)."""
        view = through.light_view(scene, self.light, frame)
        self.eye, self.target, self.fov = view["eye"], view["target"], view["fov"]

    def set_mode(self, mode: str):
        if mode not in ("free", "shot"):
            raise ValueError(f'viewport mode "{mode}": use "free" or "shot" (or look_through a light)')
        if mode == "shot" and not self.camera:
            raise ValueError("viewport: this shot has no camera to look through")
        self.mode = mode

    # --- moving the free camera
    def _polar(self):
        back = _sub(self.eye, self.target)
        dist = max(math.hypot(*back), 1e-6)
        yaw = math.degrees(math.atan2(back[0], back[2]))
        pitch = math.degrees(math.asin(max(-1.0, min(1.0, back[1] / dist))))
        return dist, yaw, pitch

    def _place(self, dist, yaw, pitch):
        y, p = math.radians(yaw), math.radians(pitch)
        back = [math.cos(p) * math.sin(y), math.sin(p), math.cos(p) * math.cos(y)]
        self.eye = _add(self.target, back, dist)

    def orbit(self, dx: float, dy: float, pivot=None):
        dist, yaw, pitch = self._polar()
        new_pitch = max(-89.0, min(89.0, pitch + dy * ORBIT_DEG))
        if pivot is None:
            return self._place(dist, yaw - dx * ORBIT_DEG, new_pitch)
        # the same turn of the view as round the target, made round the pivot: eye and target both turn about it
        back = _norm(_sub(self.eye, self.target))
        tilt, turn = _norm(_cross(back, [0.0, 1.0, 0.0])), [0.0, 1.0, 0.0]

        def spin(p):
            v = _rotate(_rotate(_sub(p, pivot), tilt, new_pitch - pitch), turn, -dx * ORBIT_DEG)
            return _add(pivot, v)
        self.eye, self.target = spin(self.eye), spin(self.target)

    def pan(self, dx: float, dy: float, height: int):
        """Slide by (dx, dy) picture pixels of a picture `height` pixels tall: what is under the pointer stays under it."""
        dist = self._polar()[0]
        scale = 2 * dist * math.tan(math.radians(self.fov / 2)) / max(height, 1)
        forward = _norm(_sub(self.target, self.eye))
        right = _norm(_cross(forward, [0.0, 1.0, 0.0]))
        up = _cross(right, forward)
        move = _add([-dx * scale * r for r in right], up, dy * scale)
        self.eye, self.target = _add(self.eye, move), _add(self.target, move)

    def zoom(self, steps: float):
        dist, yaw, pitch = self._polar()
        self._place(max(1e-3, dist * ZOOM_STEP ** steps), yaw, pitch)

    # --- the request
    def request(self, frame: int, width: int, height: int) -> dict:
        """The camera part of an Engine.view / Engine.pick request."""
        base = {"frame": frame, "width": width, "height": height}
        if self.mode == "shot":
            return {"camera": self.camera, **base}
        return {"eye": [round(x, 6) for x in self.eye], "target": [round(x, 6) for x in self.target],
                "fov": round(self.fov, 4), **base}
