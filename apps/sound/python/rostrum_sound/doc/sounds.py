"""The sounds a track can be given, in one place: the plain recorded instruments, the synth presets, the synth wave, modelled
instruments, the drum kits and the spoken voices. A sound is one key ("builtIn:piano", "synth", "model:guitar", "kit:drums",
"voice:ryan"); `fields(key)` is what it sets on a track (the instrument and the field that names it). `track.set {sound: key}`
changes a track's sound this way (its notes, hits and settings stay) and its name follows unless the person renamed it. The
Library's Add, the track panel's Sound picker and agents all read this one list. The picker order is the recorded instruments
first (grouped as in names.BUILT_IN_GROUPS), then the synth presets, the synth wave, the modelled instruments, the kits, the
voices, and last the classic synthesized voices (`classic.*`). A name that plays the same sound as a listed one
(names.BUILT_IN_ALIASES: grandPiano, feltPiano, wurlitzer …) is accepted everywhere but listed once.
"""
from __future__ import annotations

import re

from .. import names, voice

# What a new track of a sound is called, by default (the Library's Add uses it too).
KIT_NAME, VOICE_NAME, SYNTH_NAME = "Drums", "Voice", "Synth"
# Plain words for the instruments whose name alone would not say what they are.
LABELS_OF = {"guitar": "Nylon guitar", "acousticGuitar": "Steel guitar", "electricGuitar": "Electric guitar", "bass": "Bass guitar",
             "strings": "String section", "basses": "Double basses", "horn": "French horn", "warmPad": "Warm pad"}


def spaced(name: str) -> str:
    """"grandPiano" -> "Grand piano"."""
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(name)).replace("_", " ").strip()
    return words[:1].upper() + words[1:].lower()


def built_in_label(name: str) -> str:
    return "Classic " + spaced(name[8:]).lower() if name.startswith("classic.") else LABELS_OF.get(name) or spaced(name)


def _all() -> dict:
    """{key: (label, fields, default track name, group)} in the order a picker lists them."""
    groups = names.BUILT_IN_GROUPS
    classic = groups["Classic (synthesized)"]
    out = {f"builtIn:{b}": (built_in_label(b), dict(instrument="builtIn", builtIn=b), built_in_label(b), g)
           for g, bs in groups.items() if bs is not classic for b in bs}
    out["synth"] = ("Synth", dict(instrument="synth"), SYNTH_NAME, "Synth")
    out.update({f"model:{m}": (f"{spaced(m)} (modelled)", dict(instrument="model", model=m), spaced(m), "Modelled instruments") for m in names.MODELS})
    out.update({f"kit:{k}": (names.KIT_WORDS[k], dict(instrument="kit", kit=k), KIT_NAME, "Drum kits") for k in names.KITS})
    out.update({f"voice:{v}": (f"Voice: {voice.speaker_name(v)}", dict(instrument="voice", voice=v), VOICE_NAME, "Voices") for v in voice.VOICES})
    out.update({f"builtIn:{b}": (built_in_label(b), dict(instrument="builtIn", builtIn=b), built_in_label(b), "Classic (synthesized)") for b in classic})
    return out


SOUNDS = _all()
KEYS = list(SOUNDS)
LABELS = {k: v[0] for k, v in SOUNDS.items()}
# Instruments whose track the Sound picker can change (a file-based or plug-in instrument has its own file field).
PICKABLE = ["builtIn", "synth", "kit", "model", "voice"]
VALID = {"any": [{"is": ["instrument", f]} for f in PICKABLE]}
KIT_KEYS = {"kit": "kit:drums", "kit:synth": "kit:classic"}        # the one-kit days: a key an older script or agent may still give


def canonical(key: str) -> str:
    """The listed key of a sound key: an alias name (builtIn:feltPiano) -> builtIn:piano; an old kit key -> its kit."""
    if key.startswith("builtIn:") and key[8:] in names.BUILT_IN_ALIASES:
        return f"builtIn:{names.BUILT_IN_ALIASES[key[8:]]}"
    return KIT_KEYS.get(key, key)


def known(key: str) -> bool:
    return canonical(key) in SOUNDS


def fields(key: str) -> dict:
    """What the sound sets on a track (a new copy each call). An alias key keeps its own name on the track."""
    if key.startswith("builtIn:") and key[8:] in names.BUILT_IN_ALIASES:
        return dict(instrument="builtIn", builtIn=key[8:])
    return dict(SOUNDS[canonical(key)][1])


def default_name(key: str) -> str:
    return SOUNDS[canonical(key)][2]


def key_of(track: dict) -> str | None:
    """The sound a track has now (None for a track with no pickable sound); an alias name shows as the sound it plays."""
    form = track.get("instrument")
    if form == "synth":
        return form
    if form == "kit":
        return f"kit:{track.get('kit') or 'drums'}" if f"kit:{track.get('kit') or 'drums'}" in SOUNDS else None
    if form in ("builtIn", "model", "voice"):
        key = canonical(f"{form}:{track.get(form)}")
        return key if key in SOUNDS else None
    return None


def follows(track: dict) -> bool:
    """The track's name is still its sound's own: a person who renamed it (or a script that named it) keeps that name."""
    key = key_of(track)
    names_ = {default_name(key), spaced(track.get(track.get("instrument"), ""))} if key else set()
    return not track.get("name") or track["name"] in names_


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
    return [] if len(allowed(track)) < 2 else [{"value": k, "label": LABELS[k], "group": SOUNDS[k][3]} for k in allowed(track)]
