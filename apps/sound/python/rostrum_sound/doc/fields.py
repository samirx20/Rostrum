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
TONE_WORDS = {"neutral": "Off", "sub-boost": "Bass boost", "voice-clarity": "Clear voice", "radio": "Old radio"}   # the rest read as they are
FIELDS = {
    "doc": [
        N("tempo", 20, 400, "Time", "bpm"),
        V.time("length", group="Time", nullable=True,
               help="How long the mix is (a time); left out or null = the last sound + 2 s."),
        Param.toggle("ringOut", group="Time", importance="secondary", label="Ring out", default=True,
                     valid_when={"not": IS("length", None)},
                     help="Sounds still ringing at the song's Length (a held chord's release, a cymbal, an echo) play on "
                          "until they die away, and the song ends there; a note held past the Length is let go at it. "
                          "Off: the song ends at its Length, cutting what still sounds."),
        Param.toggle("endFade", group="Time", importance="secondary", label="Soft end", default=True,
                     valid_when={"all": [{"not": IS("length", None)}, IS("ringOut", False)]},
                     help="The song's last tenth of a second fades out, so notes still ringing at its Length stop softly "
                          "instead of with a click. Off: the sound stops dead at the Length."),
        N("gridStart", 0, 600, "Time", "s", imp="deep", default=0, label="Bar 1 starts",
          help="The file time (seconds) where bar 1 / beat 0 begins; left out = 0. Music before it is a pickup, written "
               "in seconds. Moves the whole beat grid without changing the tempo (script: downbeat(bar(21), at=36.0))."),
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
        Param.color("colour", group="Track", importance="secondary", label="Colour", display="swatch",
                    help="The track's colour on the Timeline and Mixer (a hex like #4aa3ff); optional."),
        *PL.INSTRUMENT,
        Param.toggle("evenKit", group="Instrument", importance="deep", label="Even kit", shown="script",
                     valid_when=IS("instrument", "kit"),
                     help="Each drum at its measured starting level against the kick and snare, and each hit's first "
                          "milliseconds held within 15 dB of its loudness, so one drum's spike does not pull the master "
                          "down. Off: the kit as recorded."),
        V.volume("volume", "Mix", help="Fader gain (1 = as recorded)."), N("pan", **PAN, group="Mix"),
        Param.toggle("mute", group="Mix"), Param.toggle("solo", group="Mix"), FB.OUTPUT,
        N("reverb", 0, 1, "Mix", imp="secondary", help="Send to the master's track reverb (a gain: 1 = 0 dB).", display="db"),
        Param.choice("tone", names.TONES, group="Mix", importance="secondary", labels=TONE_WORDS, label="Tone filter",
                     help="One filter over the whole track: muffled (as if behind a wall), warm, bass boost, bright, clear voice, "
                          "old radio; off leaves it as it is."),
        *PL.EXPRESSION,
    ],
    "note": [
        V.pitch("pitch", group="Note", help='"D4", "F#3", "Bb2", a MIDI number, or a list (a chord).'),
        V.time("at", group="Note"), V.length("dur", tied=True, group="Note", label="Length",
                                           help='Seconds, {"beats": n}, or tied: {"to": "#land"} ends it at a time or marker, '
                                                '"next" holds it until the next note on the track.'),
        N("vel", 0, 1, "Note", label="Velocity", display="percent"), N("pan", **PAN, group="Note", imp="deep"),
        *PL.NOTE,
    ],
    "hit": [
        V.drum("drum", group="Hit", help="A drum name or a GM key number."), V.time("at", group="Hit"),
        N("vel", 0, 1, "Hit", label="Velocity", display="percent"), N("pan", **PAN, group="Hit", imp="deep"),
        N("tune", 0.25, 4, "Hit", "×", imp="secondary", default=1,
          help="Pitch of the drum, as a ratio: 1× as it is, 2× an octave up, 0.5× an octave down (classic kit only)."),
        N("decay", 0.1, 4, "Hit", "×", imp="secondary", default=1, label="Ring time",
          help="How long the drum rings, as a ratio of its usual: 1× as it is, 2× twice as long."),
    ],
    "clip": [
        Param.text("media", group="Clip", label="File", control="file",
                   help="A path relative to the project folder (media/take.wav), or an absolute path to a file kept elsewhere.",
                   filters=["Sound files (*.wav *.flac *.mp3 *.ogg *.aif *.aiff)"]), V.time("at", group="Clip"),
        N("in", 0, None, "Clip", "s", label="Starts from"),
        V.length("length", group="Clip", help="How much of the file plays; left out = to its end."),
        V.volume("volume", "Clip"), N("pitch", -24, 24, "Clip", "semitones", "secondary", label="Pitch and speed", help="Tape-style: pitch and speed change together (the screen's Pitch with Keep speed off)."),
        N("shift", -24, 24, "Clip", "semitones", "secondary", label="Pitch only", help="Pitch shift keeping the length (the screen's Pitch with Keep speed on)."),
        N("stretch", 0.25, 4, "Clip", "×", "secondary", default=1, help="Length factor keeping the pitch (2 = twice as long); the clip lasts length × stretch."),
        Param.text("group", group="Clip", importance="deep", label="Layer name",
                   help="Clips of one track with the same layer name are one layered sound: moving or re-levelling one moves them all (clip.set_one changes just one). Shown once clips are layered together (Ctrl+G); an agent sets it with clip.set.",
                   valid_when={"all": [{"not": IS("group", None)}, {"not": IS("group", "")}]}),
        N("pan", **PAN, group="Clip", imp="secondary"),
        N("panTo", **PAN, group="Clip", imp="deep", label="Pan to", help="Pan at the clip's end (a sweep; agents set it, and it shows once a clip has one: the screen has one Pan).",
          when={"not": IS("panTo", None)}),
        N("fadeIn", 0, 600, "Fades", "s", label="Fade in"), N("fadeOut", 0, 600, "Fades", "s", label="Fade out"),
        N("reverb", 0, 1, "Clip", imp="secondary", display="db"),
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
    "effect": [Param.choice("effect", effects.TYPES, group="Effect", label="Effect type", labels=effects.WORDS),
               Param.toggle("bypass", group="Effect", importance="secondary"), *effects.params("effect"),
               plugins.record(IS("effect", "plugin"))],
    "marker": [Param.text("name", group="Marker"), V.time("at", group="Marker"),
               Param.color("colour", group="Marker", importance="secondary", label="Colour", display="swatch", shown="changed",
                           help="The marker's colour on its tag (a hex like #4cc38a); optional.")],
    "master": [
        V.volume("volume", "Master"),
        Param.toggle("normalize", group="Loudness", label="Normalize"),
        N("loudness", -60, 0, "Loudness", "LUFS", when=IS("normalize", True), label="Loudness target",
          help="Integrated loudness (LUFS) the whole mix is made to: -14 suits streaming, -23 broadcast."),
        N("truePeak", -12, 0, "Loudness", "dBTP", "secondary", label="Loudest peak allowed",
          help="True peak ceiling (dBTP): no moment of the mix goes above it, so it never distorts after re-encoding."),
        Param.toggle("gentle", group="Loudness", label="Gentle limiting",
                     help="On: the limiter pulls the loudest moments down by at most Most limiting; a mix that would "
                          "need more is turned down as a whole instead (the balance stays, the loudness lands under "
                          "its target and the render says by how much). Off: the limiter pulls as hard as it must."),
        N("maxLimit", 0, 12, "Loudness", "dB", "secondary", when=IS("gentle", True), label="Most limiting",
          help="The most the limiter may pull the loudest moment down (dB): 1-2 keeps the master clean."),
        N("glue", 0, 1, "Master", imp="secondary", label="Smooth the mix", display="percent",
          help="Glue compression: gently squeezes the whole mix so the parts sit together."),
        Param.choice("reverb", names.SPACES, labels=names.SPACE_WORDS, group="Spaces", importance="secondary", label="Master reverb"),
        Param.choice("trackReverbSpace", names.SPACES, labels=names.SPACE_WORDS, group="Spaces", importance="secondary",
                     label="Track reverb space"),
        N("fadeIn", 0, 600, "Fades", "s", "secondary", label="Fade in"),
        N("fadeOut", 0, 600, "Fades", "s", "secondary", label="Fade out"),
        Param.toggle("safetyClip", group="Master", importance="deep", label="Safety clip"),
    ],
}
# What a new item stores (switch fields always, so valid_when reads a real value).
DEFAULTS = {
    "doc": dict(tempo=120, beatsPerBar=4, sampleRate=48000, ringOut=True),
    "track": dict(instrument="none", **PL.SWITCHES, volume=1, pan=0, mute=False, solo=False, reverb=0,
                  tone="neutral", output=names.MASTER_OUT, evenKit=True),
    **FB.DEFAULTS,
    **FM.DEFAULTS,
    "note": dict(vel=0.8),
    "hit": dict(vel=0.85),
    "clip": dict(**{"in": 0}, volume=1, **FC.DEFAULTS),
    "line": dict(seed=1, volume=1),
    "marker": {},
    "master": dict(volume=1, normalize=False, loudness=-16, truePeak=-1, gentle=True, maxLimit=2, glue=0, reverb="dry",
                   trackReverbSpace="hall", fadeIn=0, fadeOut=0, safetyClip=True),
}
# A number's own default is what a new item stores: the panel's double-click puts the value back to it (the kit's rule).
for _type, _params in FIELDS.items():
    FIELDS[_type] = [dataclasses.replace(p, default=DEFAULTS[_type][p.name]) if p.type == "number" and p.default is None
                     and p.name in DEFAULTS.get(_type, {}) and isinstance(DEFAULTS[_type][p.name], (int, float)) else p
                     for p in _params]
# The field that holds each instrument form's value (the form's name).
INSTRUMENT_FIELD = {k: k for k in names.INSTRUMENTS if k != "none"}
REQUIRED = {"duck": ["under"], "note": ["pitch", "at", "dur"], "hit": ["drum", "at"], "clip": ["media", "at"], "line": ["text", "at"], "marker": ["name", "at"], **FM.REQUIRED}


def params(type_: str, required=False) -> list[Param]:
    """The type's Params; with required=True, copies where the item's must-have fields are required (for .add)."""
    need = REQUIRED.get(type_, []) if required else []
    return [dataclasses.replace(p, required=True) if p.name in need else p for p in FIELDS[type_]]
