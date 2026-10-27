"""Resolving the document's values per frame: keys, rigs, aims, stick, pivots, follow and mirrored copies, and every item's world
transform (compile.py's `_Frames`). An item on 2s or 3s (its `timing`) holds each value for 2 or 3 frames, counted
from the shot's start. Frame n is at n / fps seconds; the one evaluator and easing are rostrum_core.keys'.
"""
from __future__ import annotations

from rostrum_core.keys import keys_of

from . import aim, fields as F, follow, mirror, rigs

PIVOT = ("px", "py", "pz")                     # document-only: Position is where the pivot is; the core gets the origin
TIMING = "timing"                              # stepped timing: Frames.values holds the values


class Frames:
    """Every item's resolved values and world transform, per frame; aims, follows and sticks resolved lazily (an aim
    at an item needs that item's world position, which may need its parent's aim first)."""

    def __init__(self, data: dict, frames: range, fps: float, folder=None):
        self.frames, self.fps, self.items, self.parent, self.folder = frames, fps, {}, {}, folder
        self.data = data                                       # the document (clay_detail reads its shots)
        stack = [(i, None) for i in data.get("items", [])]
        while stack:
            item, parent = stack.pop()
            self.items[item["id"]], self.parent[item["id"]] = item, parent
            stack += [(c, item["id"]) for c in item.get("children", [])]
        self._world, self._values, self._busy, self._step = {}, {}, set(), {}
        self.rides, self.riding = {}, set()                    # follow.ride's per-item moves, frame by frame
        self._shift = {}                                       # (id, f) -> how far a stick moved x y z (parent space)

    def step(self, id_: str) -> int:
        """Frames each value holds (Timing): the item's own On 2s / On 3s, else its nearest group's, else 1."""
        if id_ not in self._step:
            own = F.STEPS.get(self.items[id_].get(TIMING, "smooth"), 1)
            parent = self.parent[id_]
            self._step[id_] = own if own > 1 or not parent else self.step(parent)
        return self._step[id_]

    def held(self, id_: str, f: int) -> int:
        """The frame whose values frame f shows: the first of its block of 2 or 3 when the item steps, else f."""
        n = self.step(id_)
        return self.frames[0] + (f - self.frames[0]) // n * n if n > 1 else f

    def values(self, id_: str, f: int) -> dict:
        if (f0 := self.held(id_, f)) != f:
            return self._values.setdefault((id_, f), self.values(id_, f0))   # held from its block's first frame
        if (id_, f) not in self._values:
            if (id_, f) in self._busy:
                raise ValueError(f"{id_}: its aim or stick depends on itself (it aims at or sticks to something "
                                 "inside it, or two items aim at each other through their parents)")
            self._busy.add((id_, f))
            try:
                self._values[(id_, f)] = self._resolve(id_, f)
            finally:
                self._busy.discard((id_, f))
        return self._values[(id_, f)]

    def _resolve(self, id_: str, f: int) -> dict:
        item, t = self.items[id_], f / self.fps
        if item.get("mirror"):                               # a mirrored copy: all the original's (mirror.py)
            return mirror.values(self, id_, f)
        v = {p.name: item.get(p.name, p.default) for p in F.FIELDS[item["type"]]}
        for prop in F.KEYED_TOGGLES & v.keys():
            v[prop] = bool(v[prop])                          # a still Visible left as 1.0 / 0.0 by key.clear
        for prop in {k["prop"] for k in item.get("keys", [])}:
            v[prop] = F.key_value_at(item["type"], prop, keys_of(item, prop), t)
        if item["type"] == "rig":
            v.update(rigs.transform(v, t))
        elif item["type"] == "light" and v["kind"] == "dome":     # a dome only turns around up (light_fields.py)
            v["rx"], v["ry"], v["rz"] = 0.0, v["turn"], 0.0
        elif v["aim"] != "none":
            v["rx"], v["ry"], v["rz"] = self._aim(id_, v, f)
        if v.get("stick"):
            own = [v["x"], v["y"], v["z"]]
            v.update(follow.stuck(self, id_, v, f))
            self._shift[(id_, f)] = [v[k] - o for k, o in zip(("x", "y", "z"), own)]
        if any(v.get(p) for p in PIVOT):
            v.update(zip(("x", "y", "z"), pivoted(v)))
        if v.get("follow"):
            v.update(follow.followed(self, id_, v, f))
        return v

    def world(self, id_: str, f: int):
        if (id_, f) not in self._world:
            parent = self.parent[id_]
            pw = self.world(parent, f) if parent else aim.IDENTITY
            self._world[(id_, f)] = aim.compose(pw, aim.local(self.values(id_, f)))
        return self._world[(id_, f)]

    def carrier(self, id_: str, f: int):
        """The item's SEEN placement: the transform that carries its own x y z (its pivot's place) and its own axes into
        the world as it is drawn — its parent's world, shifted by a stick, carried by a follow's ride. For an item with
        neither it is the parent's world. The gizmo stands and drags through this; pick and look read the compiled
        scene, which is built from the same values (`values`), so all three agree."""
        parent = self.parent[id_]
        m = self.world(parent, f) if parent else aim.IDENTITY
        v = self.values(id_, f)                                # resolves the stick shift and the ride first
        if (shift := self._shift.get((id_, self.held(id_, f)))) and any(shift):
            m = aim.compose(m, (aim.IDENTITY[0], shift))
        if v.get("follow"):
            m = aim.compose(follow.ride(self, id_, f), m)
        return m

    def _aim(self, id_: str, v: dict, f: int):
        if v["aim"] == "point":
            target = [v["aimX"], v["aimY"], v["aimZ"]]
        else:
            if v["aimItem"] not in self.items:
                raise ValueError(f'{id_}: aims at "{v["aimItem"]}", which is not an item')
            target = aim.point(self.world(v["aimItem"], f), [0.0, 0.0, 0.0])
        parent = self.parent[id_]
        pw = self.world(parent, f) if parent else aim.IDENTITY
        try:
            return aim.aim_rotation(pw, [v["x"], v["y"], v["z"]], target, v["roll"])
        except ValueError as e:
            raise ValueError(f"{id_} at frame {f}: can't aim: {e}") from None


def world_at_start(data: dict, id_: str):
    """An item's world transform at time 0 (aims resolved): where an operation places things inside a group."""
    return Frames(data, range(0, 1), 1.0).world(id_, 0)


def seen(data: dict, id_: str, frame: int, fps: float, start: int = 0):
    """`Frames.carrier` of one item at one frame of a shot starting at frame `start` (stepped timing counts from it),
    for a screen or a tool that has the document, not a compiled shot."""
    return Frames(data, range(min(start, frame), frame + 1), fps).carrier(id_, frame)


def pivoted(v: dict) -> list[float]:
    """The item's origin in its parent's space when its pivot (px py pz, in its own space) sits at x y z: the turn and
    scale happen around the pivot, so x y z − (turn · scale)(pivot)."""
    lin = aim.local({**v, "x": 0.0, "y": 0.0, "z": 0.0})
    off = aim.point(lin, [v["px"], v["py"], v["pz"]])
    return [v[k] - o for k, o in zip(("x", "y", "z"), off)]
