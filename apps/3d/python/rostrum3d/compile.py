"""The compiler: one shot of the document → the scene description the C++ core builds its USD stage from
(ENGINE_CONTRACT.md § 2). Every field is present (defaults filled in), colours are linear, aims are turned into
rx ry rz, and every animated field is baked to one value per frame, start..end inclusive, at the shot's fps.
Frame n is at n / fps seconds; the one evaluator and easing are rostrum_core.keys' (the same keys as 2D).
"""
from __future__ import annotations

from rostrum_core.keys import keys_of, track_value

from . import aim, fields as F
from .colors import linear

FORMAT, VERSION = "rostrum-3d-scene", 1
AIM_FIELDS = {"aim", "aimX", "aimY", "aimZ", "aimItem"}      # document-only: the compiler resolves them
ROTATION = ("rx", "ry", "rz")


def _shot(data: dict, shot_id: str) -> dict:
    shots = data.get("shots", [])
    shot = next((s for s in shots if s["id"] == shot_id), None)
    if shot is None:
        raise ValueError(f'no shot "{shot_id}"; there are: {", ".join(s["id"] for s in shots) or "none (shot.add)"}')
    return shot


def shot_info(data: dict, shot_id: str) -> dict:
    """{id, camera (item id), fps, start, end (frames, inclusive), width, height} of a shot."""
    s = _shot(data, shot_id)
    start, end = round(s["start"] * s["fps"]), round(s["end"] * s["fps"]) - 1
    if not s.get("camera"):
        raise ValueError(f'shot "{shot_id}" has no camera yet (shot.set camera=<camera id>)')
    if end < start:
        raise ValueError(f'shot "{shot_id}" is shorter than one frame at {s["fps"]} fps')
    return {"id": s["id"], "camera": s["camera"], "fps": s["fps"], "start": start, "end": end,
            "width": s["width"], "height": s["height"]}


class _Frames:
    """Every item's resolved values and world transform, per frame; aims resolved lazily (an aim at an item needs
    that item's world position, which may need its parent's aim first)."""

    def __init__(self, data: dict, frames: range, fps: float):
        self.frames, self.fps, self.items, self.parent = frames, fps, {}, {}
        stack = [(i, None) for i in data.get("items", [])]
        while stack:
            item, parent = stack.pop()
            self.items[item["id"]], self.parent[item["id"]] = item, parent
            stack += [(c, item["id"]) for c in item.get("children", [])]
        self._world, self._values, self._busy = {}, {}, set()

    def values(self, id_: str, f: int) -> dict:
        if (id_, f) not in self._values:
            item, t = self.items[id_], f / self.fps
            v = {p.name: item.get(p.name, p.default) for p in F.FIELDS[item["type"]]}
            for prop in {k["prop"] for k in item.get("keys", [])}:
                v[prop] = track_value(keys_of(item, prop), t)
            if v["aim"] != "none":
                v["rx"], v["ry"], v["rz"] = self._aim(id_, v, f)
            self._values[(id_, f)] = v
        return self._values[(id_, f)]

    def world(self, id_: str, f: int):
        if (id_, f) not in self._world:
            parent = self.parent[id_]
            pw = self.world(parent, f) if parent else aim.IDENTITY
            self._world[(id_, f)] = aim.compose(pw, aim.local(self.values(id_, f)))
        return self._world[(id_, f)]

    def _aim(self, id_: str, v: dict, f: int):
        if (id_, f) in self._busy:
            raise ValueError(f"{id_}: its aim depends on itself (it aims at something inside it, or two items aim "
                             "at each other through their parents)")
        self._busy.add((id_, f))
        try:
            if v["aim"] == "point":
                target = [v["aimX"], v["aimY"], v["aimZ"]]
            else:
                if v["aimItem"] not in self.items:
                    raise ValueError(f'{id_}: aims at "{v["aimItem"]}", which is not an item')
                target = aim.point(self.world(v["aimItem"], f), [0.0, 0.0, 0.0])
            parent = self.parent[id_]
            pw = self.world(parent, f) if parent else aim.IDENTITY
            try:
                return aim.aim_rotation(pw, [v["x"], v["y"], v["z"]], target)
            except ValueError as e:
                raise ValueError(f"{id_} at frame {f}: can't aim: {e}") from None
        finally:
            self._busy.discard((id_, f))


def _out(p, value):
    if p.type == "color":
        return linear(value)
    return round(value, 6) if isinstance(value, float) else value


def _node(item: dict, fr: _Frames) -> dict:
    type_, first = item["type"], fr.frames[0]
    params = [p for p in F.FIELDS[type_] if p.name not in AIM_FIELDS]
    v0 = fr.values(item["id"], first)
    node = {"id": item["id"], "type": type_, "props": {p.name: _out(p, v0[p.name]) for p in params}}
    animated = {k["prop"] for k in item.get("keys", [])} - AIM_FIELDS
    per_frame = {}
    if item.get("aim", "none") != "none":
        per_frame = {r: [fr.values(item["id"], f)[r] for f in fr.frames] for r in ROTATION}
        animated |= {r for r, vals in per_frame.items() if max(vals) - min(vals) > 1e-9}
    anim = {}
    for p in params:
        if p.name in animated:
            vals = per_frame.get(p.name) or [fr.values(item["id"], f)[p.name] for f in fr.frames]
            anim[p.name] = [_out(p, x) for x in vals]
    if anim:
        node["anim"] = anim
    if type_ == "import":
        node["props"]["parts"] = [{"path": pt["path"], "material": pt["material"], "visible": pt["visible"]}
                                  for pt in item.get("parts", [])]
    if type_ in F.HOLDERS:
        node["children"] = [_node(c, fr) for c in item.get("children", [])]
    return node


def describe(data: dict, shot_id: str) -> dict:
    """The contract § 2 scene of one shot."""
    info, shot = shot_info(data, shot_id), _shot(data, shot_id)
    frames = range(info["start"], info["end"] + 1)
    fr = _Frames(data, frames, info["fps"])
    cam = fr.items.get(info["camera"])
    if cam is None or cam["type"] != "camera":
        raise ValueError(f'shot "{shot_id}": its camera "{info["camera"]}" is not a camera in this document')
    mat_params = F.FIELDS["material"]
    return {
        "format": FORMAT, "version": VERSION,
        "shot": {k: info[k] for k in ("id", "fps", "start", "end")},
        "world": {"background": linear(shot["background"]), "environment": None},
        "materials": [{"id": m["id"], "props": {p.name: _out(p, m.get(p.name, p.default)) for p in mat_params}}
                      for m in data.get("materials", [])],
        "items": [_node(i, fr) for i in data.get("items", [])],
    }
