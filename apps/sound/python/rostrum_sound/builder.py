"""What a Sound script builds with: a song, its tracks (notes, chords, hits, clips, effects, automation), markers
and the master. Every value is checked by the same Params the operations use, so a script can't write what an
operation would refuse; an unknown name fails at once. Ids are stable (same script, same ids): written ids win,
the rest come from content (`doc/ids.py`) when the tree is made, after tempo and markers are known.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes, did_you_mean
from rostrum_core.conditions import describe, holds

from .doc import blank
from .doc import effects as FX
from .doc import fields as FD
from .doc import ids
from .doc.registry import MASTER_ID

INSTRUMENT_KEYS = ("builtIn", "sfz", "kit", "kitSfz")


def _checked(type_, given: dict, where: str, base: dict | None = None) -> dict:
    """`given` checked against the type's fields (unknown names and bad values fail), merged onto `base`."""
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
        if p and given[k] is not None and not holds(p.valid_when, out):
            raise RostrumError(codes.BAD_ARGUMENT, where, f'"{k}"', f"only applies when {describe(p.valid_when)}")
    return out


class _Inserts:
    """Something that takes effects and automation: a track, a clip, the master."""
    LANES = ("volume", "pan")

    def _init_inserts(self, where):
        self.where, self.effects, self.lanes = where, [], {}

    def effect(self, type_, id=None, **fields):
        """Add an effect at the end of this one's inserts: effect("eq", bands=[...]), effect("reverb", mix=0.3)."""
        if type_ not in FX.TYPES:
            raise RostrumError(codes.BAD_ARGUMENT, self.where, f'effect "{type_}"', "is not an effect type",
                               FX.TYPES, did_you_mean(type_, FX.TYPES))
        item = _checked("effect", {"effect": type_, **fields}, f"{self.where} › effect {type_}",
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

    def _insert_items(self, own_id, taken):
        fx = []
        for id_, item in self.effects:
            id_ = id_ or ids.effect(own_id, item["effect"], taken)
            taken.add(id_)
            fx.append({"id": id_, "type": "effect", **item})
        lanes = [{"id": ids.lane(own_id, k), "type": "automation", "lane": k, "points": v}
                 for k, v in self.lanes.items()]
        return {"effects": fx, "automation": lanes}


class Clip(_Inserts):
    LANES = ()

    def __init__(self, fields, id_):
        self.fields, self.id = fields, id_
        self._init_inserts(f"clip {fields['media']}")


class Track(_Inserts):
    def __init__(self, song, id_, fields):
        self.song, self.id, self.notes, self.hits, self.clips = song, id_, [], [], []
        given = dict(fields)
        if "instrument" not in given:
            kinds = [k for k in INSTRUMENT_KEYS if given.get(k) is not None]
            given["instrument"] = kinds[0] if len(kinds) == 1 else "none"
        self.fields = _checked("track", given, f"track {id_}", {"name": id_, **FD.DEFAULTS["track"]})
        self._init_inserts(f"track {id_}")

    def set(self, **fields):
        self.fields = _checked("track", fields, f"track {self.id}", self.fields)
        return self

    def note(self, pitch, at, dur, vel=None, pan=None, id=None):
        """One note: note("D4", at=beat(0), dur=beats(2), vel=0.7). A list of pitches is a chord."""
        self.notes.append((id, _checked("note", dict(pitch=pitch, at=at, dur=dur, vel=vel, pan=pan),
                                        f"track {self.id} › note", FD.DEFAULTS["note"])))
        return self

    def chord(self, pitches, at, dur, vel=None, pan=None, id=None):
        return self.note(list(pitches), at, dur, vel, pan, id)

    def hit(self, drum, at, vel=None, pan=None, tune=None, decay=None, id=None):
        """One drum hit: hit("kick", at=beat(0))."""
        self.hits.append((id, _checked("hit", dict(drum=drum, at=at, vel=vel, pan=pan, tune=tune, decay=decay),
                                       f"track {self.id} › hit", FD.DEFAULTS["hit"])))
        return self

    def clip(self, media, at, in_=None, id=None, **fields) -> Clip:
        """Recorded audio: clip(r"C:\\...\\door.wav", at=3.0, in_=0.4, length=1.2). Returns the clip (for .effect)."""
        c = Clip(_checked("clip", {"media": media, "at": at, "in": in_, **fields}, f"track {self.id} › clip",
                          FD.DEFAULTS["clip"]), id)
        self.clips.append(c)
        return c

    def item(self, root, taken) -> dict:
        def place(type_, key, entries, make):
            out = []
            for id_, f in entries:
                id_ = id_ or make(f)
                taken.add(id_)
                out.append({"id": id_, "type": type_, **f})
            return {key: out}
        where = f"track {self.id}"
        out = {"id": self.id, "type": "track", **self.fields}
        out |= place("note", "notes", self.notes, lambda f: ids.note(self.id, f["at"], root, taken, where))
        out |= place("hit", "hits", self.hits, lambda f: ids.hit(self.id, f["drum"], f["at"], root, taken, where))
        clips = []
        for c in self.clips:
            cid = c.id or ids.clip(self.id, c.fields["at"], root, taken, where)
            taken.add(cid)
            clips.append({"id": cid, "type": "clip", **c.fields, "effects": c._insert_items(cid, taken)["effects"]})
        return {**out, "clips": clips, **self._insert_items(self.id, taken)}


class Master(_Inserts):
    LANES = ("volume",)

    def __init__(self):
        self.fields = dict(FD.DEFAULTS["master"])
        self._init_inserts("master")

    def __call__(self, **fields):
        """master(loudness=-16, truePeak=-1, glue=0.2): giving a loudness target turns normalize on."""
        if fields.get("loudness") is not None and "normalize" not in fields:
            fields["normalize"] = True
        self.fields = _checked("master", fields, "master", self.fields)
        return self


class Song:
    def __init__(self):
        self.root = {k: v for k, v in blank().items() if k not in ("tracks", "markers", "master")}
        self.tracks: list[Track] = []
        self.markers: list[dict] = []
        self.master = Master()

    def set(self, **fields):
        self.root = _checked("doc", fields, "song", self.root)

    def track(self, id, **fields) -> Track:
        if any(t.id == id for t in self.tracks):
            raise RostrumError(codes.BAD_ARGUMENT, "script", f'track "{id}"', "is made twice")
        self.tracks.append(Track(self, id, fields))
        return self.tracks[-1]

    def marker(self, name, at, id=None):
        self.markers.append({"id": id or ids.marker(name), "type": "marker",
                             **_checked("marker", {"name": name, "at": at}, f"marker {name}")})

    def tree(self) -> dict:
        root = {**self.root, "markers": self.markers}
        taken = {m["id"] for m in self.markers} | {t.id for t in self.tracks} | {MASTER_ID}
        holders = [*self.tracks, self.master, *(c for t in self.tracks for c in t.clips)]
        taken |= {i for h in holders for i, _ in getattr(h, "notes", []) + getattr(h, "hits", []) + h.effects if i}
        taken |= {c.id for t in self.tracks for c in t.clips if c.id}
        tracks = [t.item(root, taken) for t in self.tracks]
        master = {"id": MASTER_ID, "type": "master", **self.master.fields,
                  **self.master._insert_items(MASTER_ID, taken)}
        return {"id": "root", "type": "doc", **self.root, "tracks": tracks, "markers": self.markers,
                "master": [master]}
