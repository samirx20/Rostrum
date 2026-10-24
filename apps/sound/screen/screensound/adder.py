"""Adding a track is choosing its sound (DESIGN.md decision 3): the Sounds panel's list of what a track can start
from — instruments, drum kits, the microphone, voices — searched by words and narrowed by kind chips. Using one is
one `track.add` call (one undo step, what an agent would call), then the new track is selected so the Editor and
the settings panel show it. With a track of the same kind selected (an instrument for a notes track, a kit for a drum
track, a voice for a voice track) the panel asks first and then changes that track's sound instead (`swap`: one
`track.set`; the notes stay). The person's own sound files are the library (library_panel.py), listed under "My
sounds". Exposed to QML as `adder`.
"""
from __future__ import annotations

import re

from PySide6.QtCore import Property, QObject, Slot
from rostrum_sound import names
from rostrum_sound.voice import VOICES

from rostrum_core.marker_times import write as marker_time

from .cards import FAMILY, spaced

# Kind chips, in order ("mine": the person's own library, drawn by the panel from `soundLibrary`).
KINDS = [("", "All"), ("instrument", "Instruments"), ("drums", "Drums"), ("record", "Record"), ("voice", "Voice"),
         ("mine", "My sounds")]
# What a sound adds beyond its name (shown under it; "" when there is nothing to add, and `note` hides a repeat of the name).
SAID = {"feltPiano": "Soft and close", "warmPad": "Slow start", "analogStrings": "Smooth ensemble",
        "spiccatoStrings": "Short, bouncy", "choirPad": "Held notes", "cinematicBrass": "Big, filmic",
        "glassMarimba": "Glassy, bright"}


NO_HEAR = {"voice": "A voice is made from a line you type, so there is nothing to hear here. Add it, type a line, then press Play.",
           "record": ""}        # kinds with no preview (a microphone or a file has nothing to play before it is used)


def _said(name: str) -> str:
    """"grandPiano" -> "Grand piano"."""
    return spaced(name).capitalize()


def _plain(label: str) -> str:
    """The name for a sentence ("Add voice: Ryan"): only the first letter drops, so names stay as typed."""
    return label[:1].lower() + label[1:]


def _entry(key, label, what, kind, fields, arm=False) -> dict:
    return {"key": key, "label": label, "what": what, "kind": kind, "fields": fields, "arm": arm}


def _entries() -> list[dict]:
    """Every sound a new track can start from: {key, label, what, kind, fields, arm}."""
    out = [_entry(f"builtIn:{b}", _said(b), SAID.get(b, ""), "instrument",
                  {"name": _said(b), "instrument": "builtIn", "builtIn": b}) for b in names.BUILT_INS]
    out.append(_entry("synth", "Synth", "A simple synth: saw, square, sine", "instrument",
                      {"name": "Synth", "instrument": "synth"}))
    out += [_entry(f"model:{m}", _said(m), FAMILY.get(m, ""), "instrument",
                   {"name": _said(m), "instrument": "model", "model": m}) for m in names.MODELS]
    out.append(_entry("kit", "Drum kit", "Kick, snare, hats, toms: a row for each drum", "drums",
                      {"name": "Drums", "instrument": "kit"}))
    out.append(_entry("mic", "Microphone", "Record your voice or an instrument (ready to record)", "record",
                      {"name": "Recording", "instrument": "none"}, arm=True))
    out.append(_entry("files", "Sound files", "Recordings and loops", "record",
                      {"name": "Audio", "instrument": "none"}))
    out += [_entry(f"voice:{v}", f"Voice: {_said(v)}", "", "voice",
                   {"name": "Voice", "instrument": "voice", "voice": v}) for v in VOICES]
    return out


ENTRIES = _entries()
PLAYS = {"instrument": ("builtIn", "sfz", "synth", "model", "plugin"), "drums": ("kit", "kitSfz"), "voice": ("voice",)}
OLD_KEYS = {"piano": "builtIn:grandPiano", "strings": "builtIn:analogStrings", "pad": "builtIn:warmPad",   # `add-track`
            "bass": "builtIn:subBass", "drums": "kit", "voice": "voice:ryan", "audio": "files"}


def placed_at(b, lead: float = 0.0):
    """(time, marker name) for a sound placed at the playhead whose moment comes `lead` seconds into it (a
    recording's onset): that moment lands on the playhead. On a marker the time is tied to
    it ("#logo lands", "#logo lands-2"; the selected marker first), so it follows when the marker moves."""
    here = sorted((m for m in b._view["markers"] if abs(m["t"] - b._t) < 1e-3),
                  key=lambda m: m["id"] not in b.selectedIds)
    if here and here[0]["t"] - lead >= 0:
        return marker_time(here[0]["name"], -lead), here[0]["name"]
    return round(max(0.0, b._t - lead), 4), ""


def _note(e: dict) -> str:
    """The description, only when it tells this sound apart: it holds a word the name does not ("Warm pad" / "Warm pad"
    says nothing twice) and no other sound says the same ("Struck bar" under three mallets says nothing)."""
    own = set(re.findall(r"\w+", e["label"].lower()))
    if not set(re.findall(r"\w+", e["what"].lower())) - own:
        return ""
    return e["what"] if sum(x["what"] == e["what"] for x in ENTRIES) == 1 else ""


def find(text: str, kind: str) -> list[dict]:
    """The entries whose words hold every word typed, of that kind ("" = all)."""
    words = text.lower().split()
    return [{**{k: v for k, v in e.items() if k != "fields"}, "note": _note(e), "hearable": e["kind"] not in NO_HEAR,
             "noHear": NO_HEAR.get(e["kind"], "")} for e in ENTRIES
            if (not kind or e["kind"] == kind) and all(w in f"{e['label']} {e['what']} {e['kind']}".lower() for w in words)]


def _entry_of(key: str) -> dict | None:
    key = OLD_KEYS.get(key, key)
    return next((e for e in ENTRIES if e["key"] == key), None)


class Adder(QObject):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge

    @Property("QVariantList", constant=True)
    def kinds(self):
        return [{"value": v, "label": label} for v, label in KINDS]

    @Slot(str, str, result="QVariantList")
    def find(self, text, kind):
        return find(text, kind)

    @Slot(str, result="QVariantMap")
    def match(self, key):
        """{track, from, to} when the selection's track plays the same kind of sound as entry `key` (the panel then
        offers to change it); {} when using the entry makes a new track."""
        e, t = _entry_of(key), self._selected_track()
        if not e or not t or t.get("instrument", "none") not in PLAYS.get(e["kind"], ()):
            return {}
        return {"track": t["id"], "from": t.get("name") or t["id"], "to": e["label"]}

    @Slot(str, str, result=bool)
    def swap(self, key, track_id):
        """Change that track's sound to entry `key` (one `track.set`, one undo step; its notes stay). A track still
        named after its old sound takes the new sound's name."""
        b, e = self.bridge, _entry_of(key)
        t = b.doc.item(track_id)
        args = {k: v for k, v in e["fields"].items() if k != "name"}
        old = next((x for x in ENTRIES if all(t.get(k) == v for k, v in x["fields"].items() if k != "name")), None)
        if old and t.get("name") == old["fields"]["name"]:
            args["name"] = e["fields"]["name"]
        return b._guard(lambda: b._apply([{"op": "track.set", "target": [track_id], "args": args}],
                                         f"Change sound to {_plain(e['label'])}"))

    def _selected_track(self) -> dict | None:
        doc, i = self.bridge.doc, self.bridge.selected
        while i and doc.has(i) and doc.item(i)["type"] != "track":
            i = doc.parent_of(i)[0] if doc.item(i)["type"] not in ("doc", "master", "marker") else ""
        return doc.item(i) if i and doc.has(i) else None

    @Slot(str, result=bool)
    def add(self, key):
        """A new track with that sound (one undo step), selected; false (and said, red) when it can't be made."""
        e = _entry_of(key)
        if e is None:
            self.bridge._fail(f'Error: add track: no sound "{key}".')
            return False
        b = self.bridge

        def go():
            before = {t["id"] for t in b.doc.data.get("tracks", [])}
            b._apply([{"op": "track.add", "args": dict(e["fields"])}], f"Add {_plain(e['label'])}" + ("" if e["kind"] == "voice" else " track"))
            new = [t["id"] for t in b.doc.data.get("tracks", []) if t["id"] not in before]
            if new:
                b.select(new[0])
        return b._guard(go)
