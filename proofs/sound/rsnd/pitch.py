"""Note names and General MIDI drum keys -> numbers the engine reads (A4 = 440 Hz)."""
import re

_STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE = re.compile(r"^([A-Ga-g])([#b]*)(-?\d+)$")

# General MIDI percussion keys (what an SFZ drum kit on GM keys answers to).
GM_DRUMS = {
    "kick": 36, "rim": 37, "snare": 38, "clap": 39, "hat": 42, "pedalHat": 44, "openHat": 46,
    "tomLow": 45, "tom": 47, "tomHigh": 50, "crash": 49, "cymbal": 49, "ride": 51, "china": 52,
    "rideBell": 53, "splash": 55, "crash2": 57, "ride2": 59,
}

# The engine's built-in synthesized kit (instruments/voices: anything else plays as a rim).
SYNTH_DRUMS = ("kick", "snare", "clap", "hat", "openHat", "cymbal", "tom", "rim")


def midi(note) -> float:
    """'C4' = 60, 'F#3', 'Bb2', or a MIDI number as is."""
    if isinstance(note, (int, float)):
        return float(note)
    m = _NOTE.match(str(note).strip())
    if not m:
        raise ValueError(f'"{note}" is not a note name (like "D3", "F#4", "Bb2") or a MIDI number')
    letter, acc, octave = m.groups()
    shift = acc.count("#") - acc.count("b")
    return float((int(octave) + 1) * 12 + _STEPS[letter.upper()] + shift)


def freq(note) -> float:
    """A note's frequency in Hz (equal temperament, A4 = 440)."""
    return 440.0 * 2.0 ** ((midi(note) - 69.0) / 12.0)


def gm_drum(name) -> float:
    """A drum name's GM key frequency (an SFZ kit maps keys, the engine plays notes by frequency)."""
    if isinstance(name, (int, float)):
        return freq(name)
    if name not in GM_DRUMS:
        raise ValueError(f'drum "{name}" is not one of {sorted(GM_DRUMS)} (or pass a GM key number)')
    return freq(GM_DRUMS[name])
