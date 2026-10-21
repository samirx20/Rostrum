"""Every name the Sound document accepts, in one place (engine contract `rostrum-sound-schedule/1`).

The engine's `describe` request is the authority on these lists: the lead checks them against it, and a name
added to the engine is added here (and only here). Effect fields and their defaults live in `doc/effects.py`.
"""
from __future__ import annotations

CONTRACT = "rostrum-sound-schedule/1"

TONES = ["neutral", "muffled", "warm", "sub-boost", "bright", "voice-clarity", "radio"]
FREEVERB_SPACES = ["freeverb.room", "freeverb.hall", "freeverb.cathedral"]
SPACES = ["dry", "room", "hall", "cathedral", "shimmer", *FREEVERB_SPACES]
EQ_SHAPES = ["lowshelf", "highshelf", "peak", "lowpass", "highpass", "notch"]
BUILT_INS = ["feltPiano", "grandPiano", "warmPad", "analogStrings", "spiccatoStrings", "choirPad",
             "cinematicBrass", "subBass", "shepardRiser", "glassMarimba"]
KITS = ["synth"]
SYNTH_DRUMS = ["kick", "snare", "clap", "hat", "openHat", "cymbal", "tom", "rim"]
# Only the names the contract spells out; the engine's `describe` (gmDrums) has the full list. A GM key
# number (27 … 87) is always accepted.
GM_DRUMS = ["kick", "snare", "hat", "openHat", "crash", "ride", "tom"]
GM_KEYS = (27, 87)

# The forms a track's instrument takes ("none": a track of recorded clips only).
INSTRUMENTS = ["none", "builtIn", "sfz", "kit", "kitSfz"]
# Which track / master values an automation lane may drive.
TRACK_LANES = ["volume", "pan"]
MASTER_LANES = ["volume"]
