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
KINDS = [("", "All"), ("instrument", "Instruments"), ("drums", "Drums"), ("record", "Mic and files"), ("voice", "Voice"),
         ("mine", "My sounds")]
# What a sound adds beyond its name (shown under it; "" when there is nothing to add, and `note` hides a repeat of the name).
SAID = {"feltPiano": "Soft and close", "warmPad": "Slow start", "analogStrings": "Smooth ensemble",
        "spiccatoStrings": "Short, bouncy", "choirPad": "Held notes", "cinematicBrass": "Big, filmic",
        "glassMarimba": "Glassy, bright", "grandPiano": "Full, clear and even", "subBass": "Deep, one low line",
        "marimba": "Wooden bars, round and warm", "vibraphone": "Metal bars, soft shimmer",
        "glockenspiel": "Small metal bars, bright and high", "tubularBell": "Long, ringing bell tones"}


NO_HEAR = {"voice": "A voice is made from a line you type: add it, type a line, then press Play.",
           "record": ""}        # kinds with no preview (a microphone or a file has nothing to play before it is used)


def _said(name: str) -> str:
    """"grandPiano" -> "Grand piano"."""
    return spaced(name).capitalize()


def _plain(e: dict) -> str:
    """The sound for a history line ("Add grand piano track", "Add voice Ryan"): a voice's name keeps its capitals."""
    return f"voice {e['label']}" if e["kind"] == "voice" else e["label"][:1].lower() + e["label"][1:]


def _person(v: str) -> str:
    """"uncle_fu" -> "Uncle Fu": a voice is a name, so every word has a capital."""
    return " ".join(w.capitalize() for w in spaced(v).split())


# The second line of a row that has nothing of its own to say, so every row has the same two-line shape.
LINE_TWO = {"instrument": "Instrument", "drums": "Drum kit", "record": "Recording", "voice": "Spoken from a line you type"}


def _entry(key, label, what, kind, fields, arm=False) -> dict:
    return {"key": key, "label": label, "what": what, "kind": kind, "fields": fields, "arm": arm}


def _entries() -> list[dict]:
    """Every sound a new track can start from: {key, label, what, kind, fields, arm}."""
    out = [_entry(f"builtIn:{b}", _said(b), SAID.get(b, ""), "instrument",
                  {"name": _said(b), "instrument": "builtIn", "builtIn": b}) for b in names.BUILT_INS]
    out.append(_entry("synth", "Synth", "A simple synth: saw, square, sine", "instrument",
                      {"name": "Synth", "instrument": "synth"}))
    out += [_entry(f"model:{m}", _said(m), SAID.get(m, FAMILY.get(m, "")), "instrument",
                   {"name": _said(m), "instrument": "model", "model": m}) for m in names.MODELS]
    out.append(_entry("kit", "Drum kit", "Kick, snare, hats, toms: a row for each drum", "drums",
                      {"name": "Drums", "instrument": "kit"}))
    out.append(_entry("mic", "Microphone", "Record your voice or an instrument (ready to record)", "record",
                      {"name": "Recording", "instrument": "none"}, arm=True))
    out.append(_entry("files", "Sound files", "Recordings and loops", "record",
                      {"name": "Audio", "instrument": "none"}))
    out += [_entry(f"voice:{v}", _person(v), "", "voice",
                   {"name": "Voice", "instrument": "voice", "voice": v}) for v in VOICES]
    return out


ENTRIES = _entries()
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
    return [{**{k: v for k, v in e.items() if k != "fields"}, "note": _note(e) or LINE_TWO.get(e["kind"], ""), "hearable": e["kind"] not in NO_HEAR,
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
            b._apply([{"op": "track.add", "args": dict(e["fields"])}], f"Add {_plain(e)}" + ("" if e["kind"] == "voice" else " track"))
            new = [t["id"] for t in b.doc.data.get("tracks", []) if t["id"] not in before]
            if new:
                b.select(new[0])
        return b._guard(go)
