"""The mix's routing in a script: a bus (a channel several tracks feed), a track's sends to buses and its ducks (dips
under other tracks). Each is checked by the same Params as `bus.add` / `send.add` / `duck.add`; the document's lists
(`buses`, `sends`, `ducks`) are rebuilt from the script like every other list, so a removed line disappears on re-run.

    verb = bus("verb", volume=0.8); verb.effect("reverb", space="hall", mix=1.0)
    keys = track("keys", builtIn="piano", output="verb")        # plays to the bus instead of the master
    keys.send("verb", level=0.3); bass.duck(under=["kick"], depth=0.5)
    vo = track("vo", role="dialogue"); music.duck(depth=0.7)    # no `under`: every dialogue track, whole lines (dialogue.py)
"""
from __future__ import annotations

from .builder_parts import Inserts, checked
from .doc import fields as FD
from .doc import ids


class Bus(Inserts):
    LANES = ("volume", "pan")

    def __init__(self, id_, fields):
        self.id = id_
        self.fields = checked("bus", {"name": id_, **fields}, f"bus {id_}", {**FD.DEFAULTS["bus"], "name": id_})
        self.init_inserts(f"bus {id_}")

    def item(self, taken) -> dict:
        taken.add(self.id)
        return {"id": self.id, "type": "bus", **self.fields, **self.insert_items(self.id, taken)}


class Routing:
    """What a track adds to the mix: `send` and `duck` (mixed into `Track`)."""

    def _routing(self) -> list:
        return self.__dict__.setdefault("routes", [])

    def send(self, bus, level=None, pre=None):
        """Feed `bus` with part of this track: send("verb", level=0.3)."""
        self._routing().append(("send", checked("send", {"bus": bus, "level": level, "pre": pre}, f"track {self.id} › send",
                                                FD.DEFAULTS["send"])))
        return self

    def duck(self, under=None, depth=None, attack=None, release=None, hold=None, voice=None, lookahead=None):
        """Dip this track while the tracks in `under` sound: duck(under=["kick"], depth=0.5). No `under`: under every
        dialogue track (role="dialogue", or a voice track), for whole lines; none in the song fails the render loudly."""
        given = {"under": list(under or ()), "depth": depth, "attack": attack, "release": release, "hold": hold, "voice": voice,
                 "lookahead": lookahead}
        self._routing().append(("duck", checked("duck", given, f"track {self.id} › duck", FD.DEFAULTS["duck"])))
        return self

    def routing_items(self, taken) -> dict:
        out = {"sends": [], "ducks": []}
        for kind, fields in self._routing():
            id_ = ids.effect(self.id, kind, taken)
            taken.add(id_)
            out[kind + "s"].append({"id": id_, "type": kind, **fields})
        return out
