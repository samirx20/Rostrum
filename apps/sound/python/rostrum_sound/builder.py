"""What a Sound script builds with: a song, its tracks (notes, chords, hits, clips, effects, automation), markers,
the music map (tempo and key changes, sections: builder_music.py) and the master. Every value is checked by the
same Params the operations use, so a script can't write what an operation would refuse; an unknown name fails at once. Ids are stable (same script, same ids): written ids win,
the rest come from content (`doc/ids.py`) when the tree is made, after tempo and markers are known.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from . import expression as EX
from . import names, script_ops
from .builder_music import MusicMap
from .builder_parts import Clip, Inserts, checked
from .doc import blank
from .doc import fields as FD
from .doc import ids, markers
from .doc.check import playing
from .doc.kind import facts as item_facts
from .doc.registry import MASTER_ID

INSTRUMENT_KEYS = tuple(FD.INSTRUMENT_FIELD)


class Track(Inserts):
    LANES = tuple(names.TRACK_LANES)

    def __init__(self, song, id_, fields):
        self.song, self.id, self.notes, self.hits, self.clips = song, id_, [], [], []
        self.human, self.phrases = None, []
        given = dict(fields)
        if "instrument" not in given:
            kinds = [k for k in INSTRUMENT_KEYS if given.get(k) is not None]
            given["instrument"] = kinds[0] if len(kinds) == 1 else "none"
        self.fields = checked("track", given, f"track {id_}", {"name": id_, **FD.DEFAULTS["track"]})
        self.init_inserts(f"track {id_}")

    def set(self, **fields):
        # The same facts the document asks of a track (its lanes), from what this builder holds so far.
        facts = item_facts({"type": "track", "automation": [{"lane": k} for k in self.lanes]})
        self.fields = checked("track", fields, f"track {self.id}", self.fields, facts)
        return self

    def __getattr__(self, verb):           # t.feel(swing=0.55): the document's own track.<verb> (script_ops.py)
        if verb.startswith("_") or (call := script_ops.method(self, verb)) is None:
            raise AttributeError(f"'Track' object has no attribute '{verb}'")
        return call

    def note(self, pitch, at, dur=None, vel=None, pan=None, id=None, end=None, **playing_):
        """One note: note("D4", at=beat(0), dur=beats(2), vel=0.7), or one that ends on a time or a marker:
        note("D4", at="#drop+5", end="#end") (`end="#end" + beats(1)` a beat after it). A list of pitches is a chord.
        Playing fields: art, position, damping, hardness, dynamics=[(0, 0.6), (1, 1)], vibrato={...}, bend=[(0, -100), (0.1, 0)]."""
        where = f"track {self.id} › note"
        if (dur is None) == (end is None):
            raise RostrumError(codes.BAD_ARGUMENT, where, f"note {pitch!r}", "needs a length (dur=) or the time it ends at "
                               "(end=), one of them", ["dur=beats(2)", "dur=1.5 (seconds)", 'end="#end"', 'end="#end" + beats(1)', 'dur="next"'])
        dur = dur if end is None else {"to": end}
        f = checked("note", dict(pitch=pitch, at=at, dur=dur, vel=vel, pan=pan, **playing_), where,
                    FD.DEFAULTS["note"], item_facts({"type": "track", **self.fields}))    # a note asks its track
        wrong = playing({**self.fields, "id": self.id, "notes": [{"id": f"note at {at!r}", **f}]})
        if wrong:
            raise RostrumError(codes.BAD_ARGUMENT, where, f"note {pitch!r}", "; ".join(wrong))
        self.notes.append((id, f, vel is not None))
        return self

    def chord(self, pitches, at, dur=None, vel=None, pan=None, id=None, end=None, **playing_):
        return self.note(list(pitches), at, dur, vel, pan, id, end, **playing_)

    def hit(self, drum, at, vel=None, pan=None, tune=None, decay=None, id=None):
        """One drum hit: hit("kick", at=beat(0))."""
        self.hits.append((id, checked("hit", dict(drum=drum, at=at, vel=vel, pan=pan, tune=tune, decay=decay),
                                      f"track {self.id} › hit", FD.DEFAULTS["hit"]), vel is not None))
        return self

    def clip(self, media, at, in_=None, id=None, **fields) -> Clip:
        """Recorded audio: clip(r"C:\\...\\door.wav", at=3.0, in_=0.4, length=1.2). Returns the clip (for .effect)."""
        c = Clip(checked("clip", {"media": media, "at": at, "in": in_, **fields}, f"track {self.id} › clip",
                         FD.DEFAULTS["clip"]), id)
        self.clips.append(c)
        return c

    def layer(self, group, takes, at, **fields) -> list[Clip]:
        """Several takes layered as one sound: layer("door", [r"C:\\...\\thud.wav", {"media": r"C:\\...\\creak.wav", "volume": 0.4}], at=3.0).
        Each take is a file, or a dict with its own clip fields; `fields` are shared. They get group="door": moving or
        re-levelling one clip in the document moves the whole layer."""
        return [self.clip(**{"at": at, **fields, **(t if isinstance(t, dict) else {"media": t}), "group": group})
                for t in takes]

    def dynamics(self, points):
        """The track's expression lane (CC 11): [(time, level 0 … 2), …], multiplied into every note."""
        return self.automate("dynamics", points)

    def vibrato(self, points, rate=None, depth=None):
        """The mod-wheel lane (CC 1): [(time, amount 0 … 1), …]; 1 = `depth` cents at `rate` Hz."""
        self.automate("vibrato", points)
        return self.set(vibratoRate=rate, vibratoDepth=depth)

    def sustain(self, points):
        """The sustain pedal lane (CC 64): [(time, 0 up … 1 down), …]; a note released while it is down (0.5 or
        more) rings on until it lifts. A step: two points at one time, sustain([(0, 1), (bar(2), 1), (bar(2), 0)])."""
        return self.automate("sustain", points)

    def bend(self, points, range=None):
        """The pitch-wheel lane: [(time, -1 … 1), …]; 1 = up `range` semitones (2 unless set)."""
        self.automate("bend", points)
        return self.set(bendRange=range)

    def humanize(self, seed, timing=0.012, velocity=0.06):
        """Every note and hit on this track (added before or after) moved by up to ±timing s and ±velocity,
        drawn from (seed, its id): the same every run (`expression.py`)."""
        self.human = EX.humanize(seed, timing, velocity, f"track {self.id} › humanize")
        return self

    def phrase(self, start, end, vel):
        """Velocity along start … end from a curve [(0, 0.5), (1, 0.9)] (0 = start, 1 = end), for the notes and
        hits there that wrote no vel of their own. A later phrase over the same notes wins."""
        self.phrases.append(EX.phrase(start, end, vel, f"track {self.id} › phrase"))
        return self

    def _shaped(self, id_, f, own_vel, root, where):
        for ph in [] if own_vel else self.phrases:
            v = ph.velocity(f["at"], root, where)
            f = f if v is None else {**f, "vel": v}
        return self.human.apply(id_, f, root, where) if self.human else f

    def item(self, root, taken) -> dict:
        where = f"track {self.id}"

        def place(type_, key, entries, make):
            out = []
            for id_, f, own_vel in entries:
                id_ = id_ or make(f)
                taken.add(id_)
                out.append({"id": id_, "type": type_, **self._shaped(id_, f, own_vel, root, where)})
            return {key: out}
        out = {"id": self.id, "type": "track", **self.fields}
        out |= place("note", "notes", self.notes, lambda f: ids.note(self.id, f["at"], root, taken, where))
        out |= place("hit", "hits", self.hits, lambda f: ids.hit(self.id, f["drum"], f["at"], root, taken, where))
        clips = []
        for c in self.clips:
            cid = c.id or ids.clip(self.id, c.fields["at"], root, taken, where)
            taken.add(cid)
            clips.append({"id": cid, "type": "clip", **c.fields, "effects": c.insert_items(cid, taken)["effects"]})
        return {**out, "clips": clips, **self.insert_items(self.id, taken)}


class Master(Inserts):
    LANES = ("volume",)

    def __init__(self):
        self.fields = dict(FD.DEFAULTS["master"])
        self.init_inserts("master")

    def __call__(self, **fields):
        """master(loudness=-16, truePeak=-1, glue=0.2): giving a loudness target turns normalize on."""
        if fields.get("loudness") is not None and "normalize" not in fields:
            fields["normalize"] = True
        self.fields = checked("master", fields, "master", self.fields)
        return self


class Song(MusicMap):
    def __init__(self):
        self.root = {k: v for k, v in blank().items() if k not in ("tracks", "markers", "master")}
        self.tracks: list[Track] = []
        self.markers: list[dict] = []
        self.known: list[dict] = []        # the document's own markers (marker.add): read, never made, by the script
        self.master = Master()

    def set(self, **fields):
        self.root = checked("doc", fields, "song", self.root)

    def track(self, id, **fields) -> Track:
        if any(t.id == id for t in self.tracks):
            raise RostrumError(codes.BAD_ARGUMENT, "script", f'track "{id}"', "is made twice")
        if fields.get("kit") in names.OLD_KITS:
            fields = {**fields, "kit": names.OLD_KITS[fields["kit"]]}
        self.tracks.append(Track(self, id, fields))
        return self.tracks[-1]

    def marker(self, name, at, id=None):
        self.markers.append({"id": id or ids.marker(name), "type": "marker",
                             **checked("marker", {"name": name, "at": at}, f"marker {name}")})

    def marks(self) -> list[dict]:
        """The markers a time in the script can name: its own, then the document's it doesn't restate (one list
        of markers, the document's, so a marker added with marker.add is found by a later script)."""
        mine = {markers.key(m["name"]) for m in self.markers}
        return self.markers + [m for m in self.known if markers.key(m.get("name", m["id"])) not in mine]

    def tree(self) -> dict:
        root = {**self.root, "markers": self.marks()}
        taken = {m["id"] for m in self.markers} | {t.id for t in self.tracks} | {MASTER_ID}
        taken |= {i["id"] for k in ("tempos", "meters", "keys", "sections") for i in self.root.get(k, [])}
        holders = [*self.tracks, self.master, *(c for t in self.tracks for c in t.clips)]
        taken |= {e[0] for h in holders for e in getattr(h, "notes", []) + getattr(h, "hits", []) + h.effects if e[0]}
        taken |= {c.id for t in self.tracks for c in t.clips if c.id}
        tracks = [t.item(root, taken) for t in self.tracks]
        master = {"id": MASTER_ID, "type": "master", **self.master.fields,
                  **self.master.insert_items(MASTER_ID, taken)}
        return {"id": "root", "type": "doc", **self.root, "tracks": tracks, "markers": self.markers,
                "master": [master]}
