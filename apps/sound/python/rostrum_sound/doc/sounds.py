"""The sounds a track can be given, in one place: built-in instruments, the synth, played instruments, the drum kit and
the spoken voices. A sound is one key ("builtIn:warmPad", "synth", "model:guitar", "kit", "voice:ryan"); `fields(key)`
is what it sets on a track (the instrument and the field that names it). `track.set {sound: key}` changes a track's
sound this way (its notes, hits and settings stay) and its name follows unless the person renamed it. The Library's
Add, the track panel's Sound picker and agents all read this one list.
"""
from __future__ import annotations

import re

from .. import names, voice

# What a new track of a sound is called, by default (the Library's Add uses it too).
KIT_NAME, VOICE_NAME, SYNTH_NAME = "Drums", "Voice", "Synth"


def spaced(name: str) -> str:
    """"grandPiano" -> "Grand piano"."""
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(name)).replace("_", " ").strip()
    return words[:1].upper() + words[1:].lower()


def _all() -> dict:
    """{key: (label, fields, default track name)} in the order a picker lists them."""
    out = {f"builtIn:{b}": (spaced(b), dict(instrument="builtIn", builtIn=b), spaced(b)) for b in names.BUILT_INS}
    out["synth"] = ("Synth", dict(instrument="synth"), SYNTH_NAME)
    out.update({f"model:{m}": (spaced(m), dict(instrument="model", model=m), spaced(m)) for m in names.MODELS})
    out["kit"] = ("Drum kit", dict(instrument="kit"), KIT_NAME)
    out.update({f"voice:{v}": (f"Voice: {voice.speaker_name(v)}", dict(instrument="voice", voice=v), VOICE_NAME) for v in voice.VOICES})
    return out


SOUNDS = _all()
KEYS = list(SOUNDS)
LABELS = {k: v[0] for k, v in SOUNDS.items()}
# Instruments whose track the Sound picker can change (a file-based or plug-in instrument has its own file field).
PICKABLE = ["builtIn", "synth", "kit", "model", "voice"]
VALID = {"any": [{"is": ["instrument", f]} for f in PICKABLE]}


def fields(key: str) -> dict:
    """What the sound sets on a track (a new copy each call)."""
    return dict(SOUNDS[key][1])


def default_name(key: str) -> str:
    return SOUNDS[key][2]


def key_of(track: dict) -> str | None:
    """The sound a track has now (None for a track with no pickable sound)."""
    form = track.get("instrument")
    if form == "synth" or form == "kit":
        return form
    if form in ("builtIn", "model", "voice"):
        key = f"{form}:{track.get(form)}"
        return key if key in SOUNDS else None
    return None


def follows(track: dict) -> bool:
    """The track's name is still its sound's own: a person who renamed it (or a script that named it) keeps that name."""
    key = key_of(track)
    return not track.get("name") or (key is not None and track["name"] == default_name(key))


FORM_OF_CONTENT = {"notes": ("builtIn", "synth", "model"), "hits": ("kit",), "lines": ("voice",)}   # what plays each (check.py NEEDS)


def allowed(track: dict) -> list[str]:
    """The sounds this track's content can be played by: notes by an instrument, hits by the drum kit, lines by a voice;
    a track with nothing on it takes any."""
    forms = {f for key, fs in FORM_OF_CONTENT.items() if track.get(key) for f in fs}
    mine = [f for key, fs in FORM_OF_CONTENT.items() if track.get(key) for f in [key]]
    if len(mine) > 1:
        return []
    return [k for k in KEYS if not forms or k.split(":")[0] in forms]


def choices(track: dict) -> list[dict]:
    """What the panel's Sound picker lists: none when there is one sound only (a picker of one is no picker)."""
    return [] if len(allowed(track)) < 2 else [{"value": k, "label": LABELS[k]} for k in allowed(track)]
