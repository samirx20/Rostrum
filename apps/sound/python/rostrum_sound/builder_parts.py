"""The builder's shared pieces: a checked set of fields, and what takes effects and automation lanes (a track,
a clip, the master). Used by `builder.py`."""
from __future__ import annotations

from rostrum_core import RostrumError, codes, did_you_mean
from rostrum_core.conditions import describe, holds

from .doc import effects as FX
from .doc import fields as FD
from .doc import ids


def checked(type_, given: dict, where: str, base: dict | None = None, facts: dict | None = None) -> dict:
    """`given` checked against the type's fields (unknown names and bad values fail), merged onto `base`;
    `facts`: what valid_when may ask beyond the fields (doc/kind.py facts, e.g. the track has a vibrato lane)."""
    params = {p.name: p for p in FD.params(type_)}
    out = dict(base or {})
    for k, v in given.items():
        if v is None:
            continue
        if k not in params:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'"{k}"', f"is not a {type_} field", list(params),
                               did_you_mean(k, params))
        out[k] = params[k].check(v, where)
    for k in given:
        p = params.get(k)
        if p and given[k] is not None and not holds(p.valid_when, out, facts):
            raise RostrumError(codes.BAD_ARGUMENT, where, f'"{k}"', f"only applies when {describe(p.valid_when)}")
    return out


class Inserts:
    """Something that takes effects and automation: a track, a clip, the master."""
    LANES = ("volume", "pan")

    def init_inserts(self, where):
        self.where, self.effects, self.lanes = where, [], {}

    def effect(self, type_, id=None, **fields):
        """Add an effect at the end of this one's inserts: effect("eq", bands=[...]), effect("reverb", mix=0.3)."""
        if type_ not in FX.TYPES:
            raise RostrumError(codes.BAD_ARGUMENT, self.where, f'effect "{type_}"', "is not an effect type",
                               FX.TYPES, did_you_mean(type_, FX.TYPES))
        item = checked("effect", {"effect": type_, **fields}, f"{self.where} › effect {type_}",
                        {"bypass": False, **FX.defaults(type_)})
        self.effects.append((id, item))
        return self

    def automate(self, lane, points):
        """Replace a lane's points: automate("volume", [(0, 0.2), (bar(9), 1.0)])."""
        if lane not in self.LANES:
            raise RostrumError(codes.BAD_ARGUMENT, self.where, f'lane "{lane}"', "can't be automated here",
                               self.LANES)
        self.lanes[lane] = [list(p) for p in points]
        return self

    def insert_items(self, own_id, taken):
        fx = []
        for id_, item in self.effects:
            id_ = id_ or ids.effect(own_id, item["effect"], taken)
            taken.add(id_)
            fx.append({"id": id_, "type": "effect", **item})
        lanes = [{"id": ids.lane(own_id, k), "type": "automation", "lane": k, "points": v}
                 for k, v in self.lanes.items()]
        return {"effects": fx, "automation": lanes}


class Clip(Inserts):
    LANES = ()

    def __init__(self, fields, id_):
        self.fields, self.id = fields, id_
        self.init_inserts(f"clip {fields['media']}")
