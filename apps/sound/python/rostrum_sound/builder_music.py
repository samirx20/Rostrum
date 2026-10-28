"""The script layer's music map: markers, tempo changes, time signature changes, key changes and sections, checked by the same
fields the operations use (doc/fields_music.py). Mixed into `builder.Song`; the items live in the song's root lists.

`marker(name, at, shared=True)` is a project marker (the one list edit_markers changes and 2D follows): the script
names it like its own, the song's tree leaves it out, and run_script publishes it, in seconds, before the merge
(mcp/script_shared.py; `shared_asked` says which). A script itself never writes a file."""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core import ids as core_ids

from .builder_parts import checked
from .doc import ids, markers


class MusicMap:
    root: dict
    markers: list[dict]
    known: list[dict]
    shared: set[str]

    def marker(self, name, at, id=None, shared=False):
        """A marker; the same name again at the same time is the same marker (marker("hit") then moment("hit") at
        it), at another time a loud error naming both. shared=True: a project marker (published by run_script)."""
        same = next((m for m in self.markers if m["id"] == (id or ids.marker(name))), None)
        if same is not None:
            if same["at"] == at:
                return
            raise RostrumError(codes.BAD_ARGUMENT, f"marker {name}", f"at={at!r}",
                               f"is a second time for the marker \"{name}\", already at {same['at']!r}",
                               hint=f'One time per name: moment("{name}") without at uses the marker already there.')
        self.markers.append({"id": id or ids.marker(name), "type": "marker",
                             **checked("marker", {"name": name, "at": at}, f"marker {name}")})
        if shared:
            self.shared.add(markers.key(name))

    def marks(self) -> list[dict]:
        """The markers a time in the script can name: its own, then the document's it doesn't restate (one list
        of markers, the document's, so a marker added with marker.add is found by a later script)."""
        mine = {markers.key(m["name"]) for m in self.markers}
        return self.markers + [m for m in self.known if markers.key(m.get("name", m["id"])) not in mine]

    def own_markers(self) -> list[dict]:
        """The markers the song's tree holds: the script's, less the shared ones (those live in the project)."""
        return [m for m in self.markers if markers.key(m["name"]) not in self.shared]

    def shared_asked(self) -> list[tuple[str, float]]:
        """[(name, seconds)] of the shared markers, on the finished tempo map (a project marker is in seconds)."""
        root = {**self.root, "markers": self.marks()}
        return [(m["name"], markers.seconds_of(root, m["at"])) for m in self.markers if markers.key(m["name"]) in self.shared]

    def _add(self, key, type_, fields, id_, where):
        items = self.root.setdefault(key, [])
        id_ = id_ or (f"section.{fields['name']}" if type_ == "section" else
                      core_ids.counted({i["id"] for i in items}, type_))
        if any(i["id"] == id_ for i in items):
            raise RostrumError(codes.BAD_ARGUMENT, "script", f'{type_} "{id_}"', "is made twice")
        items.append({"id": id_, "type": type_, **checked(type_, fields, where)})

    def tempo_change(self, at, bpm, ramp=False, id=None):
        """From `at` (beat(32), or seconds) on, the song plays at `bpm`, until the next change; `ramp=True` glides
        from `bpm` to the next change's tempo instead of jumping there."""
        self._add("tempos", "tempo", {"at": at, "bpm": bpm, **({"ramp": True} if ramp else {})}, id,
                  f"tempo change at {at!r}")

    def meter_change(self, at, beats_per_bar, beat_unit=4, id=None):
        """From `at` (beat(32), or seconds) on, `beats_per_bar` beats of `beat_unit` in a bar (6, 8: 6/8); a new bar
        starts there."""
        self._add("meters", "meter", {"at": at, "beatsPerBar": beats_per_bar, **({"beatUnit": beat_unit} if beat_unit != 4 else {})},
                  id, f"time signature change at {at!r}")

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
            self.set(tempo=song["tempo"], beatsPerBar=song["beatsPerBar"], beatUnit=song["beatUnit"])
            for b, bpm in song["tempos"]:
                self.tempo_change({"beat": b}, bpm)
            for b, per, unit in song["meters"]:
                self.meter_change({"beat": b}, per, unit)
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
            for ln, pts in t.get("lanes", {}).items():
                tr.automate(ln, pts)
            if "bendRange" in t:
                tr.set(bendRange=t["bendRange"])
            made.append(tr)
        return made
