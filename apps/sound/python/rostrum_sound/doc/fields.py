"""Each Sound item type's fields: the Params its `<type>.set` operation takes (and the inspector shows), with
`importance` and, where a field only applies sometimes, `valid_when` (rule of individuality), plus what a new
item stores. Effects are in `effects.py`; names in `../names.py`.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param

from .. import deliver, names
from . import effects
from . import fields_buses as FB
from . import fields_cleanup as FC
from . import fields_music as FM
from . import playing as PL
from . import plugins
from . import values as V

N = V.N

IS = PL.IS

PAN = dict(lo=-1, hi=1, display="pan")
FIELDS = {
    "doc": [
        N("tempo", 20, 400, "Time", "bpm"),
        V.time("length", group="Time", help="How long the mix is (a time); left out = the last sound + 2 s."),
        N("beatsPerBar", 1, 16, "Time", imp="secondary", integer=True, label="Beats per bar"),
        Param.choice("beatUnit", [2, 4, 8, 16], group="Time", importance="secondary", label="Beat unit",
                     help="What one beat of the time signature is (its bottom number): 4 quarters, 8 eighths (6/8)."),
        Param.choice("sampleRate", list(deliver.RATE_LABELS), group="Output", importance="deep", label="Sample rate",
                     labels=deliver.RATE_LABELS, help="How finely this song's sound is stored; export uses it unless "
                                                      "you pick another."),
        Param.text("picture", group="Picture", importance="secondary", control="file",
                   filters=["Videos (*.mp4 *.mov *.webm *.mkv *.avi)"], help="What the sound is made to, shown at the playhead on the Timeline: a video file, or \"item:<id>\" for a 2D item of the project (its newest render)."),
        V.time("pictureAt", group="Picture", importance="secondary", label="Picture starts",
               valid_when={"not": {"any": [IS("picture", None), IS("picture", "")]}},
               help='When the picture\'s first frame is at: seconds, a beat, or a shared marker ("#logo"); left out = 0. '
                    "A marker moves the picture with it."),
    ],
    "track": [
        Param.text("name", group="Track", importance="secondary"),
        Param.color("colour", group="Track", importance="secondary", label="Colour",
                    help="The track's colour on the Timeline and Mixer (a hex like #4aa3ff); optional."),
        *PL.INSTRUMENT,
        V.volume("volume", "Mix", help="Fader gain (1 = as recorded)."), N("pan", **PAN, group="Mix"),
        Param.toggle("mute", group="Mix"), Param.toggle("solo", group="Mix"), FB.OUTPUT,
        N("reverb", 0, 1, "Mix", imp="secondary", help="Send to the master's track reverb.", display="percent"),
        Param.choice("tone", names.TONES, group="Mix", importance="secondary"),
        *PL.EXPRESSION,
    ],
    "note": [
        V.pitch("pitch", group="Note", help='"D4", "F#3", "Bb2", a MIDI number, or a list (a chord).'),
        V.time("at", group="Note"), V.length("dur", tied=True, group="Note", label="Length",
                                           help='Seconds, {"beats": n}, or tied: {"to": "#land"} ends it at a time or marker, '
                                                '"next" holds it until the next note on the track.'),
        N("vel", 0, 1, "Note", label="Velocity", display="percent"), N("pan", **PAN, group="Note", imp="secondary"),
        *PL.NOTE,
    ],
    "hit": [
        V.drum("drum", group="Hit", help="A drum name or a GM key number."), V.time("at", group="Hit"),
        N("vel", 0, 1, "Hit", label="Velocity", display="percent"), N("pan", **PAN, group="Hit", imp="secondary"),
        N("tune", 0.25, 4, "Hit", "×", imp="secondary", help="Pitch ratio (synth kit only)."),
        N("decay", 0.1, 4, "Hit", "×", imp="secondary", help="Factor of the hit's length."),
    ],
    "clip": [
        Param.text("media", group="Clip", label="File", control="file",
                   help="A path relative to the project folder (media/take.wav), or an absolute path to a file kept elsewhere.",
                   filters=["Sound files (*.wav *.flac *.mp3 *.ogg *.aif *.aiff)"]), V.time("at", group="Clip"),
        N("in", 0, None, "Clip", "s", label="In-point"),
        V.length("length", group="Clip", help="How much of the file plays; left out = to its end."),
        V.volume("volume", "Clip"), N("pitch", -24, 24, "Clip", "st", "secondary", label="Pitch and speed", help="Tape-style: pitch and speed change together."),
        N("shift", -24, 24, "Clip", "st", "secondary", label="Pitch only", help="Pitch shift keeping the length."),
        N("stretch", 0.25, 4, "Clip", "×", "secondary", default=1, help="Length factor keeping the pitch (2 = twice as long); the clip lasts length × stretch."),
        Param.text("group", group="Clip", importance="deep", label="Layer group", help="Clips of one track with the same group name are one layered sound: moving or re-levelling one moves them all (clip.set_one changes just one)."),
        N("pan", **PAN, group="Clip", imp="secondary"),
        N("panTo", **PAN, group="Clip", imp="deep", label="Pan to", help="Pan at the clip's end."),
        N("fadeIn", 0, 600, "Fades", "s", label="Fade in"), N("fadeOut", 0, 600, "Fades", "s", label="Fade out"),
        N("reverb", 0, 1, "Clip", imp="secondary", display="percent"),
        *FC.PARAMS,
    ],
    "line": [
        Param.text("text", group="Line", help="What is said."), V.time("at", group="Line", help="When the line "
                   "starts: seconds, {\"beat\": n} or a marker (\"#drop+0.5\")."),
        N("seed", 1, 999999, "Line", imp="secondary", integer=True, label="Take",
          help="Another whole number makes another reading of the same words."),
        V.volume("volume", "Line"), N("fadeIn", 0, 600, "Fades", "s", "secondary", label="Fade in"),
        N("fadeOut", 0, 600, "Fades", "s", "secondary", label="Fade out"),
    ],
    **FB.FIELDS,
    **FM.FIELDS,
    "effect": [Param.choice("effect", effects.TYPES, group="Effect", label="Effect type"),
               Param.toggle("bypass", group="Effect", importance="secondary"), *effects.params("effect"),
               plugins.record(IS("effect", "plugin"))],
    "marker": [Param.text("name", group="Marker"), V.time("at", group="Marker")],
    "master": [
        V.volume("volume", "Master"),
        Param.toggle("normalize", group="Loudness", label="Normalize"),
        N("loudness", -60, 0, "Loudness", "LUFS", when=IS("normalize", True), label="Loudness target",
          help="Integrated loudness (LUFS) the whole mix is made to: -14 suits streaming, -23 broadcast."),
        N("truePeak", -12, 0, "Loudness", "dBTP", "secondary", label="Loudest peak allowed",
          help="True peak ceiling (dBTP): no moment of the mix goes above it, so it never distorts after re-encoding."),
        N("glue", 0, 1, "Master", imp="secondary", label="Smooth the mix", display="percent",
          help="Glue compression: gently squeezes the whole mix so the parts sit together."),
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
    **FM.DEFAULTS,
    "note": dict(vel=0.8),
    "hit": dict(vel=0.85),
    "clip": dict(**{"in": 0}, volume=1, **FC.DEFAULTS),
    "line": dict(seed=1, volume=1),
    "marker": {},
    "master": dict(volume=1, normalize=False, loudness=-16, truePeak=-1, glue=0, reverb="dry",
                   trackReverbSpace="hall", fadeIn=0, fadeOut=0, safetyClip=True),
}
# The field that holds each instrument form's value (the form's name).
INSTRUMENT_FIELD = {k: k for k in names.INSTRUMENTS if k != "none"}
REQUIRED = {"duck": ["under"], "note": ["pitch", "at", "dur"], "hit": ["drum", "at"], "clip": ["media", "at"], "line": ["text", "at"], "marker": ["name", "at"], **FM.REQUIRED}


def params(type_: str, required=False) -> list[Param]:
    """The type's Params; with required=True, copies where the item's must-have fields are required (for .add)."""
    need = REQUIRED.get(type_, []) if required else []
    return [dataclasses.replace(p, required=True) if p.name in need else p for p in FIELDS[type_]]
