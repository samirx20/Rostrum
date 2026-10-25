"""Every name the Sound document accepts, in one place (engine contract `rostrum-sound-schedule/1`).

The engine's `describe` request is the authority on these lists: the lead checks them against it, and a name
added to the engine is added here (and only here). Effect fields and their defaults live in `doc/effects.py`.
"""
from __future__ import annotations

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
    "Piano and keys": ["piano", "electricPiano", "organ", "pipeOrgan"],
    "Guitar and bass": ["guitar", "acousticGuitar", "electricGuitar", "bass", "uprightBass"],
    "Strings": ["strings", "spiccatoStrings", "violins", "violas", "cellos", "basses", "violin", "cello", "harp"],
    "Brass and winds": ["brass", "horn", "trumpet", "trombone", "tuba", "flute", "piccolo", "oboe", "clarinet",
                        "bassoon", "saxophone"],
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
DEFAULT_BUILT_IN = "piano"
# The plain names that are synthesized (an analog preset or a classic voice): any key plays; the rest are recordings with a range.
SYNTHESIZED = [*BUILT_IN_GROUPS["Synth"], *BUILT_IN_GROUPS["Classic (synthesized)"]]
KITS = ["drums", "studio", "classic"]
OLD_KITS = {"synth": "drums"}      # the one kit there was, before the kits had names: a document or script that says it means "drums"
KIT_WORDS = {"drums": "Rock kit", "studio": "Studio kit", "classic": "Classic (synthesized) kit"}
SYNTH_DRUMS = ["kick", "snare", "clap", "hat", "openHat", "cymbal", "tom", "rim"]
# General MIDI drum names an SFZ kit on GM keys answers to (the engine's `describe` gmDrums); a GM key
# number (27 … 87) is always accepted.
GM_DRUMS = ["kick", "kick2", "rim", "snare", "clap", "snare2", "hat", "pedalHat", "openHat", "lowTom", "floorTom", "tomLow",
            "tom", "midTom", "tomHigh", "highTom", "crash", "cymbal", "ride", "china", "rideBell", "splash", "crash2", "ride2",
            "shaker"]
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


# The recorded kits ("drums", "studio") sit on General MIDI keys: every GM name, the shaker and the toms by either name; a
# GM key number is not accepted there (hits name their drum). The classic kit has its own eight.
KIT_DRUMS = GM_DRUMS


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
