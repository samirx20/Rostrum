"""Where items are, frame by frame of a shot, read from the document as the scene compiler resolves it (resolve.Frames:
keys, stepped timing, aims, sticks, follows, mirrored copies) — nothing is rendered. Per item and frame: its pivot's
world place, where that is seen through the shot camera (px), whether it is shown (Visible, its own and its groups'),
and for shapes their solid (item_bounds.solid: an oriented box) and how much of it the camera's picture holds.
"""
from __future__ import annotations

import math

from . import aim, item_bounds
from .resolve import Frames

INSIDE = ("combine", "copies")          # items inside these are inputs or sources, not drawn as themselves


def _unit(v):
    n = math.hypot(*v) or 1.0
    return [x / n for x in v]


class Camera:
    """The shot camera at one frame: `project(p)` -> (x px, y px) on the picture, None when p is not in front of it."""

    def __init__(self, fr: Frames, cam: str, f: int, width: int, height: int):
        world, v = fr.world(cam, f), fr.values(cam, f)
        self.eye, self.w, self.h = aim.point(world, [0.0, 0.0, 0.0]), width, height
        self.right, self.up, self.back = (_unit([row[k] for row in world[0]]) for k in range(3))
        self.tan_w = v["sensorWidth"] / (2 * v["focalLength"])          # the lens fits the picture's width (ops_shot_camera)
        self.tan_h, self.near = self.tan_w * height / width, v["near"]

    def project(self, p):
        d = [a - b for a, b in zip(p, self.eye)]
        depth = -sum(a * b for a, b in zip(d, self.back))
        if depth <= self.near:
            return None
        u = sum(a * b for a, b in zip(d, self.right)) / (depth * self.tan_w)
        v = sum(a * b for a, b in zip(d, self.up)) / (depth * self.tan_h)
        return (u + 1) / 2 * self.w, (1 - v) / 2 * self.h

    def holds(self, corners) -> str:
        """'in' when every corner is in the picture, 'out' when none can be (all behind, or all past one edge), else 'part'."""
        pts = [self.project(c) for c in corners]
        seen = [p for p in pts if p]
        if not seen:
            return "out"
        if len(seen) == len(pts) and all(0 <= x <= self.w and 0 <= y <= self.h for x, y in seen):
            return "in"
        if len(seen) == len(pts) and (all(x < 0 for x, _ in seen) or all(x > self.w for x, _ in seen)
                                      or all(y < 0 for _, y in seen) or all(y > self.h for _, y in seen)):
            return "out"
        return "part"


class Track:
    """The items of a shot over frames `frames` (shot frame numbers): `rows[id]` per frame {frame, world, screen, shown,
    solid, view}. `skipped[id]`: why a shape item's solid could not be measured (an import, copies)."""

    def __init__(self, data: dict, info: dict, frames: range, folder=None, sim: dict | None = None):
        self.fr = Frames(data, range(info["start"], frames.stop), info["fps"], folder)
        self.data, self.info, self.frames, self.built, self.skipped = data, info, frames, {}, {}
        if sim:                                 # mcp/motion_sim.moves: the simulated things where the stored result has them
            self.skipped.update(sim["skip"])
            self._lay_over(sim["moves"], info["start"])
        self.cams = {f: Camera(self.fr, info["camera"], f, info["width"], info["height"]) for f in frames}

    def _lay_over(self, moves: dict, s0: int):
        """A falling item's x y z rx ry rz per frame (from the shot's first frame) replace its keyed ones."""
        resolve = self.fr._resolve

        def resolved(id_: str, f: int) -> dict:
            v = resolve(id_, f)
            if per := moves.get(id_):
                v = {**v, **{k: vals[min(max(f - s0, 0), len(vals) - 1)] for k, vals in per.items()}}
            return v
        self.fr._resolve = resolved

    def ids(self) -> list[str]:
        """Every item drawn as itself (not the shot camera, not an input inside a combine or a copies item), in the document's order."""
        def walk(items):
            for item in items:
                yield item["id"]
                yield from walk(item.get("children", []))
        return [i for i in walk(self.data.get("items", [])) if i != self.info["camera"] and not self._inside(i)]

    def _inside(self, id_: str) -> bool:
        p = self.fr.parent[id_]
        return p is not None and (self.fr.items[p]["type"] in INSIDE or self._inside(p))

    def shown(self, id_: str, f: int) -> bool:
        p = self.fr.parent[id_]
        return bool(self.fr.values(id_, f).get("visible", True)) and (p is None or self.shown(p, f))

    def row(self, id_: str, f: int) -> dict:
        v = self.fr.values(id_, f)
        world = aim.point(self.fr.world(id_, f), [v.get(k, 0.0) for k in ("px", "py", "pz")])
        out = {"frame": f, "world": world, "screen": self.cams[f].project(world), "shown": self.shown(id_, f), "solid": None}
        if self.fr.items[id_]["type"] in item_bounds.SHAPES and id_ not in self.skipped:
            try:
                out["solid"] = item_bounds.solid(self.data, self.fr, id_, f, self.built)
            except ValueError as e:
                self.skipped[id_] = str(e)
        out["view"] = self.cams[f].holds(out["solid"][0]) if out["solid"] else None
        return out

    def rows(self, id_: str) -> list[dict]:
        return [self.row(id_, f) for f in self.frames]
