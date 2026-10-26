"""The pieces Sound's action entries are made from (actions.py lists them): `act` (one entry's dict), `on` (an entry on the
selected items of some kinds), the selection tests, and the kind groups. Data and plain functions, no Qt."""
from __future__ import annotations

from rostrum_sound import main_mix
from rostrum_sound.doc import select_time as ST
from rostrum_sound.doc.effects import TYPES as EFFECT_TYPES

from . import action_calls as C
from . import key_lock

EFFECTS = [t for t in EFFECT_TYPES if t != "plugin"]      # the words are effects.WORDS (one place)
CLIPS = {"note", "hit", "clip", "line"}


def act(key, label, valid_when, calls=None, shortcut="", importance="secondary", group="", menu="", do="",
        promoted_when=None, needs="", min_targets=0, release="", panel=True, on=(), amounts=(), asks=False, fit=None,
        sure=False):
    return {"key": key, "label": label, "shortcut": shortcut, "valid_when": valid_when, "importance": importance,
            "promoted_when": promoted_when, "calls": calls, "group": group, "menu": menu, "do": do, "needs": needs,
            "min_targets": min_targets, "release": release, "panel": panel, "on": on, "amounts": amounts, "asks": asks,
            "fit": fit, "sure": sure}


def on(kinds, op, **args):
    """(valid_when, calls) of an action on the selected items of `kinds`, whatever else is selected: one call per
    kind, e.g. Quantise on Select all = note.quantize on its notes + hit.quantize on its hits."""
    return (lambda f: bool(f.by_kind(kinds)),
            lambda f: [C.call(f"{k}.{op}", ids, **args) for k, ids in f.by_kind(kinds).items()])


def _inside_clip(f):
    return f.one == "clip" and any(ST.start_of(f.doc.data, c) + 1e-6 < f.playhead < ST.end_of(f.doc.data, c) - 1e-6
                                   for c in f.items)


def _can_make_main(f):
    """Nothing selected, the song is in a project and is not its main mix yet (rule of individuality: else absent)."""
    return f.count == 0 and bool(f.doc.folder) and not main_mix.is_main(f.doc.folder, f.doc.item_id)


def _outside_key(f):
    """The selection holds a note with a tone outside the key playing at its start (Fit to key leads then)."""
    return any(key_lock.outside(f.doc.data, n, ST.start_of(f.doc.data, n)) for n in f.items if n["type"] == "note")


_STEPS = (("up", 1, "Up a half step", "Up"), ("down", -1, "Down a half step", "Down"),
          ("up12", 12, "Up an octave", "Shift+Up"), ("down12", -12, "Down an octave", "Shift+Down"))
TRACK, CLIP = (lambda f: f.one == "track"), (lambda f: f.one == "clip")
NOTE_HIT, NOTE = ("note", "hit"), ("note",)
MARKER = lambda f: f.one == "marker" and f.count == 1 and isinstance(f.items[0].get("at"), (int, float))  # noqa: E731
NAMED = ("track", "bus", "marker", "section")
