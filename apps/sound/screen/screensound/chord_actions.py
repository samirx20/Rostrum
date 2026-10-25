"""Chord ▾ (Sound's SPEC § 3.9–3.11): the settings panel's one chord button, present only while notes are selected. Its
menu holds only what applies: Make a chord ▸ (each selected note a root), Invert up / down (Alt+↑ / Alt+↓), Strum… and
Arpeggio… (the kit's amounts popover). The last three need a chord in the selection: notes of one track that start
together, or one note holding several pitches (`doc/chords.py`, the one rule the operations use). No Qt.

    Strum…      Gap (ms) and Direction (Down / Up); More: Soften          note.strum
    Arpeggio…   Rate (a picker of grid steps), Pattern, Octaves; More: Gate, Seed      note.arpeggiate
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_sound.doc import chords

from . import action_calls as C
from . import key_lock
from .amount_actions import GRIDS

NOTE = ("note",)
MAKE = "Chord › Make a chord"
SHAPES = (("key", "In key", True), ("key7", "In key with 7th", True), ("major", "Major", False), ("minor", "Minor", False),
          ("sus2", "Sus2", False), ("sus4", "Sus4", False), ("power", "Power (5th)", False), ("octave", "Octave", False))
UP = Param.choice("direction", ["down", "up"], label="Direction",
                  help="Down: from the lowest note up, like a downstroke. Up: from the top note down.")
UP_LABELS = {"type": "choice", "options": [{"value": "down", "label": "Down"}, {"value": "up", "label": "Up"}]}
RATES = [g for g in GRIDS if g[0] <= 1.0]                     # an arpeggio steps at most a beat
PATTERNS = (("up", "Up"), ("down", "Down"), ("upDown", "Up and down"), ("downUp", "Down and up"),
            ("converge", "Outside in"), ("diverge", "Inside out"), ("order", "As written"), ("random", "Random"))


def notes(f) -> list[str]:
    return f.by_kind(NOTE).get("note", [])


def has_notes(f) -> bool:
    return bool(notes(f))


def has_chord(f) -> bool:
    """A chord of two or more tones among the selected notes (the operations' own grouping)."""
    return has_notes(f) and f.once("has_chord", lambda f: chords.any_chord(f.doc.data, notes(f)))


def shape_valid(needs_key: bool):
    return lambda f: has_notes(f) and (not needs_key or key_lock.has_key(f.doc.data))


def shape_calls(shape: str):
    return lambda f: [C.call("note.chord", notes(f), shape=shape)]


def invert_calls(by: int):
    return lambda f: [C.call("note.invert", notes(f), by=by)]


# ---- Strum… ------------------------------------------------------------------------------------------------------
def strum_calls(f, a=None):
    a = a or {}
    gap = abs(float(a.get("gap", 30)))
    args = {"gap": -gap if a.get("direction") == "up" else gap}
    if "soften" in a:
        args["soften"] = a["soften"]
    return [C.call("note.strum", notes(f), **args)]


def strum_fit(f, a):
    return {"gap": {"min": 0, "max": 200, "default": 30, "importance": "primary"}, "direction": UP_LABELS,
            "soften": {"importance": "secondary"}}


# ---- Arpeggio… ---------------------------------------------------------------------------------------------------
def arp_calls(f, a=None):
    a = a or {}
    args = {k: a[k] for k in ("rate", "mode", "octaves", "gate", "seed") if k in a}
    return [C.call("note.arpeggiate", notes(f), **args)]


def arp_fit(f, a):
    return {"rate": {"type": "choice", "options": [{"value": v, "label": w} for v, w in RATES], "importance": "primary"},
            "mode": {"type": "choice", "options": [{"value": v, "label": w} for v, w in PATTERNS], "importance": "primary"},
            "octaves": {"importance": "primary"}, "gate": {"importance": "secondary"}, "seed": {"importance": "secondary"}}
