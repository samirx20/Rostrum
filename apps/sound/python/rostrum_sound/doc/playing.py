"""How a track is played: the instrument choice with each form's settings (contract § 2a), a note's playing
fields (articulation, touch, expression) and the track's expression settings. `fields.py` puts them on the
item types; the Sound screen's Instruments page builds its cards from exactly these Params.

Ranges and defaults are the engine's (ENGINE_CONTRACT.md § 2a); a default here is only what a screen shows for
an unset field: the compiler writes a field only when the document holds it.
"""
from __future__ import annotations

from rostrum_core import Param

from .. import names, voice
from . import plugins
from . import values as V

N = V.N
IS = lambda name, value: {"is": [name, value]}  # noqa: E731
MODEL = IS("instrument", "model")
SYNTH = IS("instrument", "synth")
VOICE = IS("instrument", "voice")
STRUCK = {"all": [MODEL, {"not": IS("model", "violin")}]}           # every model but the bowed one
PLUCKED = {"all": [MODEL, {"any": [IS("model", m) for m in names.PLUCKED]}]}



def touch(track=True, imp="primary", group="Instrument"):
    """position / damping / hardness: a model track's defaults (conditions on its fields) or a note's own
    (conditions on its track, through the kind's facts: doc/kind.py)."""
    struck, plucked = (STRUCK, PLUCKED) if track else ({"fact": "struck"}, {"fact": "plucked"})
    return [
        N("position", 0, 0.5, group, imp=imp, when=struck, help="Where it is plucked or struck: bridge / bar "
          "end (0) … middle (0.5); plucked strings from 0.03. Not for violin."),
        N("damping", 0, 1, group, imp=imp, when=plucked, default=0,
          help="Plucked strings only: 0 rings open … 1 palm-muted."),
        N("hardness", 0, 1, group, imp="secondary" if imp == "primary" else imp, when=struck, default=0.5,
          help="Pick / mallet: soft … hard. Not for violin."),
    ]


# The synth's settings: (name, lo, hi, default, unit, importance, whole number?)
SYNTH_FIELDS = [
    ("attack", 0.001, 20, 0.3, "s", "primary", False), ("brightness", 40, 20000, 2400, "Hz", "primary", False),
    ("release", 0.001, 20, 0.8, "s", "secondary", False), ("resonance", 0, 1, 0.2, "", "secondary", False),
    ("voices", 1, 16, 3, "", "secondary", True), ("detune", 0, 100, 12, "cents", "secondary", False),
    ("decay", 0.001, 20, 0.5, "s", "deep", False), ("sustain", 0, 1, 0.8, "", "deep", False),
    ("envAmount", 0, 8, 0, "oct", "deep", False), ("octave", -3, 3, 0, "", "deep", True),
    ("drive", 0, 10, 0, "", "deep", False), ("width", 0, 1, 1, "", "deep", False),
    ("drift", 0, 30, 0, "cents", "deep", False), ("noise", 0, 1, 0, "", "deep", False),
    ("sub", 0, 1, 0, "", "deep", False),
]
SYNTH_KEYS = [f[0] for f in SYNTH_FIELDS]
TOUCH_KEYS = ["position", "damping", "hardness"]

# The picker's words (the inspector's field is narrow: about 20 characters)
INSTRUMENT_WORDS = {"none": "None (clips only)", "builtIn": "Built-in sound", "sfz": "Sampled (SFZ file)",
                    "kit": "Drum kit", "kitSfz": "Sampled drum kit", "model": "Played instrument",
                    "synth": "Synth", "voice": "Spoken voice", "plugin": "Plug-in instrument"}
INSTRUMENT = [
    Param.choice("instrument", names.INSTRUMENTS, group="Instrument", label="Instrument", labels=INSTRUMENT_WORDS,
                 help="What plays the track's notes / hits; none = recorded clips only."),
    Param.choice("builtIn", names.BUILT_INS, group="Instrument", label="Sound", valid_when=IS("instrument", "builtIn")),
    Param.text("sfz", group="Instrument", label="SFZ file", valid_when=IS("instrument", "sfz")),
    Param.toggle("legato", group="Instrument", importance="secondary", valid_when=IS("instrument", "sfz"),
                 help="Notes that overlap glide into each other (one bowed line)."),
    Param.toggle("swell", group="Instrument", importance="secondary", valid_when=IS("instrument", "sfz"),
                 help="Long notes swell in instead of starting at full level."),
    V.mapping("articulations", "articulations", group="Instrument", importance="secondary",
              valid_when=IS("instrument", "sfz"), help="Other playing styles of this instrument, each its own SFZ "
              'file ({"spiccato": "…spic.sfz"}); a note picks one with art.'),
    Param.choice("kit", names.KITS, group="Instrument", label="Drum kit", valid_when=IS("instrument", "kit")),
    Param.text("kitSfz", group="Instrument", label="SFZ drum kit", valid_when=IS("instrument", "kitSfz")),
    Param.choice("model", names.MODELS, group="Instrument", label="Model", valid_when=MODEL,
                 help="A played (procedural) instrument: plucked strings, struck bars or a bowed violin."),
    *touch(),
    Param.choice("voice", voice.VOICES, group="Instrument", label="Voice", valid_when=VOICE,
                 help="Who speaks the track's lines (a preset voice)."),
    Param.choice("language", voice.LANGUAGES, group="Instrument", label="Language", valid_when=VOICE,
                 help="The language the lines are spoken in; auto = from the text."),
    Param.text("style", group="Instrument", label="Style", valid_when=VOICE,
               help='How the voice speaks, in plain words: "warm, confident", "low and close to the microphone".'),
    Param.choice("synth", names.WAVES, group="Instrument", label="Wave", valid_when=SYNTH),
    *[N(n, lo, hi, "Instrument", unit, imp, SYNTH, whole, default) for n, lo, hi, default, unit, imp, whole
      in SYNTH_FIELDS],
    plugins.record(IS("instrument", "plugin")),
]
# The track's CC-style expression settings (its dynamics / vibrato lanes are automation lanes); shown only
# while the track has a vibrato lane (the kind's fact, kind.py).
HAS_VIBRATO = {"fact": "vibratoLane"}
EXPRESSION = [
    N("vibratoRate", 0.1, 20, "Expression", "Hz", "secondary", when=HAS_VIBRATO, default=5.5, label="Vibrato rate",
      help="Speed of the vibrato lane's wobble."),
    N("vibratoDepth", 0, 200, "Expression", "cents", "secondary", when=HAS_VIBRATO, default=25, label="Vibrato depth",
      help="How wide the vibrato lane's wobble is at 1."),
]
VIBRATO = [N("rate", 0.1, 20, "Vibrato", "Hz"), N("depth", 0, 200, "Vibrato", "cents"),
           N("delay", 0, 30, "Vibrato", "s")]
# A note's playing fields. Art and touch show only where the note's track can play them (its facts: kind.py).
NOTE = [
    Param.text("art", group="Playing", importance="secondary", label="Articulation", valid_when={"fact": "articulated"},
               help="One of the track's articulations; left out = its main SFZ file."),
    *touch(track=False, imp="secondary", group="Playing"),
    V.curve("dynamics", (0, 1), (0, 2), group="Playing", importance="deep",
            help="Swell / fade across the note: [[fraction of its length, level 0 … 2], …]."),
    V.record("vibrato", VIBRATO, "vibrato", group="Playing", importance="deep",
             help='Steady vibrato: {"rate": Hz, "depth": cents, "delay": s}.'),
    V.curve("bend", (0, None), (-2400, 2400), group="Playing", importance="deep",
            help="Pitch bend: [[seconds into the note, cents], …] (a slide, a fall, a scoop)."),
]
NOTE_KEYS = [p.name for p in NOTE]
# What a new track stores so the instrument cards' conditions read real values.
SWITCHES = dict(builtIn="grandPiano", kit="synth", model="guitar", synth="saw", voice="ryan", language="auto")  # every kind with a choice has one, so switching kind is one change
