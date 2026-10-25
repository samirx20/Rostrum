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
from rostrum_sound import names, roles
from rostrum_sound.doc import sounds
from rostrum_sound.voice import VOICES, speaker_name

from rostrum_core.marker_times import write as marker_time

from .cards import FAMILY, spaced

# Kind chips, in order ("mine": the person's own library, drawn by the panel from `soundLibrary`).
KINDS = [("", "All"), ("instrument", "Instruments"), ("drums", "Drums"), ("record", "Mic and files"), ("voice", "Voice"),
         ("mine", "My sounds")]
# What a sound adds beyond its name (shown under it; "" when there is nothing to add, and `note` hides a repeat of the name).
# An instrument says what it is in the one role table (roles.py: the words before its bracket); a few more words here.
SAID = {"marimba": "Wooden bars, round and warm", "vibraphone": "Metal bars, soft shimmer",
        "glockenspiel": "Small metal bars, bright and high", "tubularBell": "Long, ringing bell tones",
        "drums": "Rock kit: kick, snare, hats, toms, crash, ride", "studio": "Close-miked, rusty and dry",
        "classic": "Synthesized: kick, snare, clap, hats, tom, cymbal, rim"}


NO_HEAR = {"voice": "A voice is made from a line you type: add it, type a line, then press Play.",
           "record": ""}        # kinds with no preview (a microphone or a file has nothing to play before it is used)


def _said(name: str) -> str:
    """"grandPiano" -> "Grand piano"."""
    return spaced(name).capitalize()


def _plain(e: dict) -> str:
    """The sound for a history line ("Add grand piano track", "Add voice Ryan"): a voice's name keeps its capitals."""
    return f"voice {e['label']}" if e["kind"] == "voice" else e["label"][:1].lower() + e["label"][1:]


_person = speaker_name      # "uncle_fu" -> "Uncle Fu": a voice is a name (voice.py is the one place)


# The second line of a row that has nothing of its own to say, so every row has the same two-line shape.
LINE_TWO = {"instrument": "Instrument", "drums": "Drum kit", "record": "Recording", "voice": "Spoken from a line you type"}


def _entry(key, label, what, kind, fields, arm=False) -> dict:
    return {"key": key, "label": label, "what": what, "kind": kind, "fields": fields, "arm": arm}


def _built_in(key: str) -> dict:
    name = key[8:]
    role = roles.ROLES.get(key)
    what = role.sounds.split(" (")[0] if role else ""
    return _entry(key, sounds.LABELS[key], SAID.get(name, what[:1].upper() + what[1:]), "instrument",
                  {"name": sounds.default_name(key), **sounds.fields(key)})


def _entries() -> list[dict]:
    """Every sound a new track can start from: {key, label, what, kind, fields, arm}. The recorded instruments first,
    the classic synthesized voices last among the instruments (the Sound picker's order, doc/sounds.py)."""
    built_in = [k for k in sounds.KEYS if k.startswith("builtIn:")]
    out = [_built_in(k) for k in built_in if not k.startswith("builtIn:classic.")]
    out.append(_entry("synth", "Synth", "A simple synth: saw, square, sine", "instrument",
                      {"name": sounds.SYNTH_NAME, **sounds.fields("synth")}))
    out += [_entry(f"model:{m}", sounds.LABELS[f"model:{m}"], SAID.get(m, FAMILY.get(m, "")), "instrument",
                   {"name": _said(m), **sounds.fields(f"model:{m}")}) for m in names.MODELS]
    out += [_built_in(k) for k in built_in if k.startswith("builtIn:classic.")]
    out += [_entry(f"kit:{k}", sounds.LABELS[f"kit:{k}"], SAID[k], "drums",
                   {"name": sounds.KIT_NAME, **sounds.fields(f"kit:{k}")}) for k in names.KITS]
    out.append(_entry("mic", "Microphone", "Record your voice or an instrument (ready to record)", "record",
                      {"name": "Recording", "instrument": "none"}, arm=True))
    out.append(_entry("files", "Sound files", "Recordings and loops", "record",
                      {"name": "Audio", "instrument": "none"}))
    out += [_entry(f"voice:{v}", _person(v), "", "voice",
                   {"name": sounds.VOICE_NAME, **sounds.fields(f"voice:{v}")}) for v in VOICES]
    return out


ENTRIES = _entries()
OLD_KEYS = {"piano": "builtIn:piano", "strings": "builtIn:strings", "pad": "builtIn:warmPad",   # `add-track`
            "bass": "builtIn:bass", "drums": "kit:drums", "voice": "voice:ryan", "audio": "files"}


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


# the orchestra's family words: a search for the family finds every section and solo in it (critic r7: "strings"
# missed String section, Violins and Cellos)
FAMILIES = {"strings": ("strings", "spiccatoStrings", "violins", "violas", "cellos", "basses", "violin", "cello", "harp",
                        "classic.analogStrings"),
            "brass": ("brass", "horn", "trumpet", "trombone", "tuba"),
            "woodwinds": ("flute", "piccolo", "oboe", "clarinet", "bassoon", "saxophone"),
            "percussion": ("marimba", "vibraphone", "xylophone", "glockenspiel", "tubularBells", "timpani")}
FAMILY_OF = {f"builtIn:{k}": fam for fam, keys in FAMILIES.items() for k in keys}


def _holds(text: str, word: str) -> bool:
    """`word` is in `text`, or its singular is ("strings" finds "String section", "basses" finds "bass")."""
    return any(w and w in text for w in {word, word[:-1] if word.endswith("s") else "",
                                         word[:-2] if word.endswith(("ses", "xes")) else ""})


def find(text: str, kind: str) -> list[dict]:
    """The entries whose words hold every word typed (or its singular, or the entry's family: "strings", "brass",
    "woodwinds", "percussion"), of that kind ("" = all); those whose name holds them first."""
    words = text.lower().split()
    found = []
    for e in ENTRIES:
        about = f"{e['label']} {e['what']} {e['kind']} {FAMILY_OF.get(e['key'], '')}".lower()
        if (not kind or e["kind"] == kind) and all(_holds(about, w) for w in words):
            found.append((not all(_holds(e["label"].lower(), w) for w in words), len(found), e))
    return [{**{k: v for k, v in e.items() if k != "fields"}, "note": _note(e) or LINE_TWO.get(e["kind"], ""), "hearable": e["kind"] not in NO_HEAR,
             "noHear": NO_HEAR.get(e["kind"], "")} for *_, e in sorted(found, key=lambda x: x[:2])]


def _entry_of(key: str) -> dict | None:
    key = OLD_KEYS.get(key, key)
    key = sounds.canonical(key) if sounds.known(key) else key
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
            if new:                   # its outline now; the settings panel and the Editor's track once the click is drawn
                b._pick(new[:1], later=True)
                b._settle()
        return b._guard(go)
