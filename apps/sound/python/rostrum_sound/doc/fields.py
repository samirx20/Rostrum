"""Each Sound item type's fields: the Params its `<type>.set` operation takes (and the inspector shows), with
`importance` and, where a field only applies sometimes, `valid_when` (rule of individuality), plus what a new
item stores. Effects are in `effects.py`; names in `../names.py`.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param

from .. import names
from . import effects
from . import fields_buses as FB
from . import playing as PL
from . import values as V

N = V.N

IS = PL.IS



PAN = dict(lo=-1, hi=1)
FIELDS = {
    "doc": [
        N("tempo", 20, 400, "Time", "bpm"),
        V.time("length", group="Time", help="How long the mix is (a time); left out = the last sound + 2 s."),
        N("beatsPerBar", 1, 16, "Time", imp="secondary", integer=True, label="Beats per bar"),
        N("sampleRate", 22050, 192000, "Output", "Hz", "deep", integer=True, label="Sample rate"),
        Param.text("picture", group="Picture", importance="secondary", help="A video file to make the sound to (shown at the playhead on the Timeline)."),
    ],
    "track": [
        Param.text("name", group="Track", importance="secondary"),
        *PL.INSTRUMENT,
        N("volume", 0, 4, "Mix", help="Fader gain (1 = as recorded)."), N("pan", **PAN, group="Mix"),
        Param.toggle("mute", group="Mix"), Param.toggle("solo", group="Mix"), FB.OUTPUT,
        N("reverb", 0, 1, "Mix", imp="secondary", help="Send to the master's track reverb."),
        Param.choice("tone", names.TONES, group="Mix", importance="secondary"),
        *PL.EXPRESSION,
    ],
    "note": [
        V.pitch("pitch", group="Note", help='"D4", "F#3", "Bb2", a MIDI number, or a list (a chord).'),
        V.time("at", group="Note"), V.length("dur", group="Note", label="Length"),
        N("vel", 0, 1, "Note", label="Velocity"), N("pan", **PAN, group="Note", imp="secondary"),
        *PL.NOTE,
    ],
    "hit": [
        V.drum("drum", group="Hit", help="A drum name or a GM key number."), V.time("at", group="Hit"),
        N("vel", 0, 1, "Hit", label="Velocity"), N("pan", **PAN, group="Hit", imp="secondary"),
        N("tune", 0.25, 4, "Hit", imp="secondary", help="Pitch ratio (synth kit only)."),
        N("decay", 0.1, 4, "Hit", imp="secondary", help="Factor of the hit's length."),
    ],
    "clip": [
        Param.text("media", group="Clip", label="File"), V.time("at", group="Clip"),
        N("in", 0, None, "Clip", "s", label="In-point"),
        V.length("length", group="Clip", help="How much of the file plays; left out = to its end."),
        N("volume", 0, 4, "Clip"), N("pitch", -24, 24, "Clip", "st", "secondary"),
        N("pan", **PAN, group="Clip", imp="secondary"),
        N("panTo", **PAN, group="Clip", imp="deep", label="Pan to", help="Pan at the clip's end."),
        N("fadeIn", 0, 600, "Fades", "s", label="Fade in"), N("fadeOut", 0, 600, "Fades", "s", label="Fade out"),
        N("reverb", 0, 1, "Clip", imp="secondary"),
    ],
    **FB.FIELDS,
    "effect": [Param.choice("effect", effects.TYPES, group="Effect", label="Effect type"),
               Param.toggle("bypass", group="Effect", importance="secondary"), *effects.params("effect")],
    "marker": [Param.text("name", group="Marker"), V.time("at", group="Marker")],
    "master": [
        N("volume", 0, 4, "Master"),
        Param.toggle("normalize", group="Loudness", label="Normalize"),
        N("loudness", -60, 0, "Loudness", "LUFS", when=IS("normalize", True), label="Loudness target"),
        N("truePeak", -12, 0, "Loudness", "dBTP", "secondary", label="True peak ceiling"),
        N("glue", 0, 1, "Master", imp="secondary", help="Glue compression."),
        Param.choice("reverb", names.SPACES, group="Spaces", importance="secondary", label="Master reverb"),
        Param.choice("trackReverbSpace", names.SPACES, group="Spaces", importance="secondary",
                     label="Track reverb space"),
        N("fadeIn", 0, 600, "Fades", "s", "secondary", label="Fade in"),
        N("fadeOut", 0, 600, "Fades", "s", "secondary", label="Fade out"),
        Param.toggle("safetyClip", group="Master", importance="deep", label="Safety clip"),
    ],
}
# What a new item stores (switch fields always, so valid_when reads a real value).
DEFAULTS = {
    "doc": dict(tempo=120, beatsPerBar=4, sampleRate=48000),
    "track": dict(instrument="none", **PL.SWITCHES, volume=0.85, pan=0, mute=False, solo=False, reverb=0,
                  tone="neutral", output=names.MASTER_OUT),
    **FB.DEFAULTS,
    "note": dict(vel=0.8),
    "hit": dict(vel=0.85),
    "clip": dict(**{"in": 0}, volume=1),
    "marker": {},
    "master": dict(volume=1, normalize=False, loudness=-16, truePeak=-1, glue=0, reverb="dry",
                   trackReverbSpace="hall", fadeIn=0, fadeOut=0, safetyClip=True),
}
# The field that holds each instrument form's value (the form's name).
INSTRUMENT_FIELD = {k: k for k in names.INSTRUMENTS if k != "none"}
REQUIRED = {"duck": ["under"], "note": ["pitch", "at", "dur"], "hit": ["drum", "at"], "clip": ["media", "at"], "marker": ["name", "at"]}


def params(type_: str, required=False) -> list[Param]:
    """The type's Params; with required=True, copies where the item's must-have fields are required (for .add)."""
    need = REQUIRED.get(type_, []) if required else []
    return [dataclasses.replace(p, required=True) if p.name in need else p for p in FIELDS[type_]]
