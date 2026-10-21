"""The script layer's music map: tempo changes, key changes and sections, checked by the same fields the
operations use (doc/fields_music.py). Mixed into `builder.Song`; the items live in the song's root lists."""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core import ids as core_ids

from .builder_parts import checked


class MusicMap:
    root: dict

    def _add(self, key, type_, fields, id_, where):
        items = self.root.setdefault(key, [])
        id_ = id_ or (f"section.{fields['name']}" if type_ == "section" else
                      core_ids.counted({i["id"] for i in items}, type_))
        if any(i["id"] == id_ for i in items):
            raise RostrumError(codes.BAD_ARGUMENT, "script", f'{type_} "{id_}"', "is made twice")
        items.append({"id": id_, "type": type_, **checked(type_, fields, where)})

    def tempo_change(self, at, bpm, id=None):
        """From `at` (beat(32), or seconds) on, the song plays at `bpm`, until the next change."""
        self._add("tempos", "tempo", {"at": at, "bpm": bpm}, id, f"tempo change at {at!r}")

    def key(self, key, at=0, id=None):
        """The key from `at` on ("D minor", "F# major", "Bb dorian"): for agents and the screen, not heard."""
        self._add("keys", "key", {"key": key, "at": at}, id, f"key {key!r}")

    def section(self, name, at, end, id=None):
        """A named part of the song ("verse") from `at` to `end`."""
        self._add("sections", "section", {"name": name, "at": at, "end": end}, id, f"section {name}")

    def import_midi(self, path, song_map=True) -> list:
        """A MIDI file's tracks (notes; channel 10 as drum hits), markers and sections, and with song_map its tempo
        map, time signature and keys (midi/song.py). Returns the new tracks, to change their instruments."""
        from . import midi
        song = midi.read(path)
        if song_map:
            self.set(tempo=song["tempo"], beatsPerBar=song["beatsPerBar"])
            for b, bpm in song["tempos"]:
                self.tempo_change({"beat": b}, bpm)
            for b, k in song["keys"]:
                self.key(k, {"beat": b})
        names = {m["name"] for m in self.markers}
        for b, name in song["markers"]:
            self.marker(midi._free(name, names, "marker"), {"beat": b})
        parts = {s["name"] for s in self.root.get("sections", [])}
        for name, b0, b1 in song["sections"]:
            self.section(midi._free(name, parts, "section"), {"beat": b0}, {"beat": b1})
        made, taken = [], {t.id for t in self.tracks}
        for t in song["tracks"]:
            kind = "builtIn" if "builtIn" in t else "kit"
            tr = self.track(midi._free(t["name"].lower(), taken, "midi"), name=t["name"], **{kind: t[kind]})
            for n in t["notes"]:
                tr.note(**n)
            for h in t["hits"]:
                tr.hit(**h)
            made.append(tr)
        return made
