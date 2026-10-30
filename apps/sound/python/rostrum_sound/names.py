"""Every name the Sound document accepts, in one place (engine contract `rostrum-sound-schedule/1`).

The engine's `describe` request is the authority on these lists: the lead checks them against it, and a name
added to the engine is added here (and only here). Effect fields and their defaults live in `doc/effects.py`.
"""
from __future__ import annotations

import difflib
import re

CONTRACT = "rostrum-sound-schedule/1"

TONES = ["neutral", "muffled", "warm", "sub-boost", "bright", "voice-clarity", "radio"]
FREEVERB_SPACES = ["freeverb.room", "freeverb.hall", "freeverb.cathedral"]
SPACES = ["dry", "room", "hall", "cathedral", "shimmer", *FREEVERB_SPACES]
# The words a space shows in (the one place): the Freeverb ones are the same rooms with Decay, Damping and Size to set.
SPACE_WORDS = {s: f"{s.split('.')[1].capitalize()} (adjustable)" for s in FREEVERB_SPACES}
EQ_SHAPES = ["lowshelf", "highshelf", "peak", "lowpass", "highpass", "notch"]
# The plain instrument names (`builtIn`), mirrored from the engine's one table (contract/names.rs, GAP.md § 1): each plays a
# recorded instrument, an analog synth preset or, only as `classic.<name>`, the older synthesized voice. A document keeps
# the name as written; the engine resolves it when it plays. In picker order: the recorded ones first, grouped by what they are.
BUILT_IN_GROUPS = {
    "Piano and keys": ["piano", "electricPiano", "rhodes", "organ", "pipeOrgan"],
    "Guitar and bass": ["guitar", "acousticGuitar", "electricGuitar", "bass", "uprightBass"],
    "Strings": ["strings", "spiccatoStrings", "violins", "violas", "cellos", "basses", "violin", "cello", "harp"],
    "Brass and winds": ["brass", "horn", "trumpet", "mutedTrumpet", "trombone", "tuba", "flute", "piccolo", "oboe", "clarinet",
                        "bassoon", "saxophone", "harmonica"],
    "Mallets and drums": ["marimba", "vibraphone", "xylophone", "glockenspiel", "tubularBells", "timpani"],
    "Synth": ["warmPad", "subBass", "pluck", "choirPad"],
    "Classic (synthesized)": ["classic.feltPiano", "classic.grandPiano", "classic.warmPad", "classic.analogStrings",
                              "classic.spiccatoStrings", "classic.choirPad", "classic.cinematicBrass", "classic.subBass",
                              "classic.glassMarimba"],
}
# Other names that play the same sound as a listed one (the engine accepts both; a picker shows the one).
BUILT_IN_ALIASES = {
    "grandPiano": "piano", "acousticPiano": "piano", "feltPiano": "piano", "wurlitzer": "electricPiano",
    "drawbarOrgan": "organ", "nylonGuitar": "guitar", "steelGuitar": "acousticGuitar", "archtopGuitar": "acousticGuitar", "cleanGuitar": "electricGuitar",
    "electricBass": "bass", "bassGuitar": "bass", "doubleBass": "uprightBass", "analogStrings": "strings", "cinematicBrass": "brass",
    "tenorSax": "saxophone", "glassMarimba": "marimba", "pad": "warmPad",
}
BUILT_INS = [*(n for g in BUILT_IN_GROUPS.values() for n in g), *BUILT_IN_ALIASES]
# General MIDI and other common names with no recording of their own, played by the plainly nearest one (a script is
# told which: builder.Song.track). Kept small: a name with no honest near sound (harpsichord, accordion …) is still refused.
NEAREST_BUILT_IN = {
    "celesta": "glockenspiel", "musicBox": "glockenspiel", "chimes": "tubularBells",
    "brightAcousticPiano": "piano", "acousticGrandPiano": "piano", "honkyTonkPiano": "piano",
    "electricGrandPiano": "electricPiano", "electricPiano1": "electricPiano", "electricPiano2": "electricPiano",
    "stringEnsemble": "strings", "stringEnsemble1": "strings", "stringEnsemble2": "strings", "tremoloStrings": "strings",
    "orchestralHarp": "harp", "frenchHorn": "horn", "frenchHorns": "horn", "brassSection": "brass",
    "altoSax": "saxophone", "sopranoSax": "saxophone", "baritoneSax": "saxophone", "englishHorn": "oboe",
    "acousticBass": "uprightBass", "fingerBass": "bass", "pickedBass": "bass", "electricBassFinger": "bass",
    "electricBassPick": "bass", "synthBass": "subBass", "choir": "choirPad", "choirAahs": "choirPad", "voiceOohs": "choirPad",
}
DEFAULT_BUILT_IN = "piano"
# The plain names that are synthesized (an analog preset or a classic voice): any key plays; the rest are recordings with a range.
SYNTHESIZED = [*BUILT_IN_GROUPS["Synth"], *BUILT_IN_GROUPS["Classic (synthesized)"]]
KITS = ["drums", "studio", "jazz", "classic"]
OLD_KITS = {"synth": "drums"}      # the one kit there was, before the kits had names: a document or script that says it means "drums"
KIT_WORDS = {"drums": "Rock kit", "studio": "Studio kit", "jazz": "Jazz kit", "classic": "Classic (synthesized) kit"}
SYNTH_DRUMS = ["kick", "snare", "clap", "hat", "openHat", "cymbal", "tom", "rim"]
# General MIDI drum names an SFZ kit on GM keys answers to (the engine's `describe` gmDrums); a GM key
# number (27 … 87) is always accepted.
GM_DRUMS = ["kick", "kick2", "rim", "snare", "clap", "snare2", "hat", "pedalHat", "openHat", "lowTom", "floorTom", "tomLow",
            "tom", "midTom", "tomHigh", "highTom", "crash", "cymbal", "ride", "china", "rideBell", "splash", "crash2", "ride2",
            "stir", "shaker"]
GM_KEYS = (27, 87)
# Drum names agents and people reach for first, one meaning on every kit: written as the kit's own name.
# Keys are compared lower case without spaces, "-" or "_" (drum_key), so "Hi-Hat", "hi_hat" and "hihat" are one.
DRUM_ALIASES = {**{k: "hat" for k in ("hat", "hihat", "hh", "chh", "closedhat", "closedhihat", "closedhh", "hats")},
                **{k: "openHat" for k in ("openhat", "openhihat", "ohh", "openhh")},
                **{k: "kick" for k in ("kick", "bd", "kickdrum", "bassdrum")},
                **{k: "snare" for k in ("snare", "sd", "snaredrum")},
                **{k: "rim" for k in ("rim", "rimshot", "sidestick", "crossstick")},
                **{k: "clap" for k in ("clap", "handclap", "claps")},
                **{k: "pedalHat" for k in ("pedalhat", "pedalhihat", "foothat")}}
# Names that mean one drum on one kind of kit only: the check names the drum to write instead.
KIT_NEAREST = {"kit": {**{k: "cymbal" for k in ("crash", "crash2", "ride", "ride2", "ridebell", "splash", "china")},
                       **{k: "tom" for k in ("tomlow", "lowtom", "floortom", "tomhigh", "hightom", "hitom", "midtom", "tom1", "tom2", "tom3")}},
               "kitSfz": {**{k: "tomLow" for k in ("lowtom", "floortom")}, **{k: "tomHigh" for k in ("hightom", "hitom")}}}


# The recorded kits ("drums", "studio", "jazz") sit on General MIDI keys: every GM name, the shaker and the toms by either name; a
# GM key number is not accepted there (hits name their drum). The classic kit has its own eight.
KIT_DRUMS = GM_DRUMS


# The rows a kit's Editor starts with (the drums a person reaches for on it); any other drum hit adds its row.
KIT_ROWS = {"jazz": ["kick", "snare", "stir", "ride", "hat", "pedalHat", "crash", "tom"]}


def kit_rows(kit: str | None) -> list[str]:
    return KIT_ROWS.get(kit or "", SYNTH_DRUMS)


def kit_drums(kit: str | None) -> list[str]:
    """The drum names a `kit` value plays."""
    return SYNTH_DRUMS if kit == "classic" else KIT_DRUMS


def drum_key(name: str) -> str:
    return "".join(c for c in name.lower() if c not in " -_")

# The forms a track's instrument takes ("none": a track of recorded clips only; "voice": a track of spoken lines, `doc/ops_voice.py`).
INSTRUMENTS = ["none", "builtIn", "sfz", "kit", "kitSfz", "model", "synth", "voice", "plugin"]
# Procedural instruments (`{"model": …}`, contract § 2a) by how they are played: the touch fields follow from it.
PLUCKED = ["guitar", "nylonGuitar"]
BARS = ["marimba", "vibraphone", "glockenspiel", "tubularBell"]
BOWED = ["violin"]
MODELS = [*PLUCKED, *BARS, *BOWED]
WAVES = ["saw", "square", "triangle", "sine"]
# Which track / master values an automation lane may drive. The expression lanes (CC-style) compile into the
# track's `expression`; the others into its `automation`.
EXPRESSION_LANES = ["dynamics", "vibrato", "sustain", "bend"]   # CC 11, CC 1, CC 64, the pitch wheel
TRACK_LANES = ["volume", "pan", *EXPRESSION_LANES]
MASTER_LANES = ["volume"]
BUS_LANES = ["volume", "pan"]
SEND_LANES = ["level"]
ALL_LANES = [*TRACK_LANES, *SEND_LANES]
LANE_WORDS = {"volume": "Volume", "pan": "Pan", "dynamics": "Expression", "vibrato": "Vibrato", "sustain": "Sustain",
              "bend": "Pitch bend", "level": "Level"}     # what a lane is called on screen (agents' errors say these too)
# A track's or bus's `output` when it feeds the master bus (the default); otherwise a bus id.
MASTER_OUT = "master"


# Words agents reach for that the engine has no instrument of: the refusal names what to use instead (lower case, no spaces).
BUILT_IN_NEAR = {"contrabass": ["basses", "uprightBass", "doubleBass"], "doublebasses": ["basses", "uprightBass"], "bassguitar": ["bass"],
                 "epiano": ["rhodes", "electricPiano"], "fenderrhodes": ["rhodes"], "keys": ["piano", "rhodes", "electricPiano", "organ"], "grandpiano": ["piano"],
                 "sax": ["saxophone"], "altosax": ["saxophone"], "frenchhorn": ["horn"], "horns": ["horn", "brass"], "trumpets": ["trumpet", "brass"],
                 "hammond": ["organ"], "churchorgan": ["pipeOrgan"], "vibes": ["vibraphone"], "bell": ["tubularBells", "glockenspiel"],
                 "bells": ["tubularBells", "glockenspiel"], "synth": ["warmPad", "pluck", "subBass"], "lead": ["pluck", "trumpet", "flute"],
                 "choir": ["choirPad"], "orchestra": ["strings", "brass"], "drums": ["(a kit, not a builtIn: kit='drums')"],
                 "kit": ["(a kit, not a builtIn: kit='drums')"]}
SOUND_GUIDE = "inspect_guide 'agent-reference', section \"Instrument and kit names\" (every name, what it is)"


def _loose(word) -> str:
    return re.sub(r"[\s_\-]+", "", str(word)).lower()


def near_names(field: str, value, options: list[str]) -> list[str]:
    """Up to four names close to a wrong `value`: written another way (case, spaces), a word an agent reaches for, or spelled nearly."""
    key = _loose(value)
    found = [o for o in options if _loose(o) == key]
    found += [n for n in (BUILT_IN_NEAR.get(key, []) if field == "builtIn" else []) if n not in found]
    found += [o for o in options if o not in found and len(key) >= 3 and (key in _loose(o) or _loose(o) in key)]
    found += [o for o in difflib.get_close_matches(str(value), options, n=3, cutoff=0.5) if o not in found]
    return found[:4]


def nearest_built_in(name) -> str | None:
    """The built-in sound that plainly stands in for a common name Rostrum has no recording of ("celesta": glockenspiel),
    or None (a listed name, or one with no near sound)."""
    if not isinstance(name, str) or _loose(name) in {_loose(o) for o in BUILT_INS}:
        return None
    return {_loose(k): v for k, v in NEAREST_BUILT_IN.items()}.get(_loose(name))


def read_sound(fields: dict) -> dict:
    """A script's `builtIn=` / `kit=` as the document keeps it: the form's own prefix is dropped (`kit="kit:classic"` is how the
    engine's listing writes it), an old kit name is renamed, and a wrong name is refused with the close ones and the guide's list."""
    from rostrum_core import RostrumError, codes
    out = dict(fields)
    for field, options in (("builtIn", BUILT_INS), ("kit", KITS)):
        v = out.get(field)
        if not isinstance(v, str):
            continue
        if v.startswith(f"{field}:"):
            v = v.split(":", 1)[1]
        if field == "kit":
            v = OLD_KITS.get(v, v)
        if _loose(v) not in {_loose(o) for o in options}:
            close = near_names(field, v, options)
            raise RostrumError(codes.BAD_ARGUMENT, "script", f"{field}={v!r}", "is not one of the choices",
                               hint=(f"Close: {', '.join(close)}. " if close else "") + f"Every {'instrument' if field == 'builtIn' else 'kit'} name with what it is: {SOUND_GUIDE}.")
        out[field] = v
    return out
