"""Keys and the key map: music-theory facts for agents and the screen (never rendered).

A key is written "D minor", "F# major", "Bb dorian" (a tonic, then a mode). The key map is the song's key changes
(`keys[]`, type "key": {at, key}); before the first one the key is unknown (None). `scale` gives the key's notes,
`in_key` says whether a pitch belongs, `step_in_key` / `steps_in_key` walk along it (transpose by steps), `snap` moves a pitch to the nearest note of the key, `signature` /
`from_signature` turn a key into a MIDI key signature (sharps or flats, major or minor) and back; `midi` /
`pitch_name` turn a pitch ("F#3") into a MIDI number (C4 = 60) and back.
"""
from __future__ import annotations

import re

from . import times

TONICS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MODES = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10), "dorian": (0, 2, 3, 5, 7, 9, 10),
         "phrygian": (0, 1, 3, 5, 7, 8, 10), "lydian": (0, 2, 4, 6, 7, 9, 11), "mixolydian": (0, 2, 4, 5, 7, 9, 10),
         "locrian": (0, 1, 3, 5, 6, 8, 10)}
# Where each mode's tonic sits in its major scale (for a key signature): dorian is the 2nd degree, …
MODE_DEGREE = {"major": 0, "minor": 9, "dorian": 2, "phrygian": 4, "lydian": 5, "mixolydian": 7, "locrian": 11}
KEY = re.compile(r"^([A-Ga-g])(#|b)?\s+(" + "|".join(MODES) + r")$", re.IGNORECASE)
# The major key with n sharps (n < 0: flats), -7 … 7, as MIDI's key signature counts them.
SHARPS = {-7: "Cb", -6: "Gb", -5: "Db", -4: "Ab", -3: "Eb", -2: "Bb", -1: "F", 0: "C", 1: "G", 2: "D", 3: "A",
          4: "E", 5: "B", 6: "F#", 7: "C#"}
MINORS = {-7: "Ab", -6: "Eb", -5: "Bb", -4: "F", -3: "C", -2: "G", -1: "D", 0: "A", 1: "E", 2: "B", 3: "F#",
          4: "C#", 5: "G#", 6: "D#", 7: "A#"}
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PITCH = re.compile(r"^([A-Ga-g])(#|b)?(-?\d)$")
FORMS = ['"D minor"', '"F# major"', '"Bb dorian"', f"modes: {', '.join(MODES)}"]


def midi(p) -> int:
    """A pitch ("D4", "F#3", "Bb2", or a MIDI number) as a MIDI number (C4 = 60)."""
    if isinstance(p, int):
        return p
    m = PITCH.match(p)
    if m is None:
        raise ValueError(f"not a note: {p!r}")
    acc = {"#": 1, "b": -1}.get(m.group(2) or "", 0)
    return (int(m.group(3)) + 1) * 12 + TONICS[m.group(1).upper()] + acc


FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def pc_name(k: int, key: str | None = None) -> str:
    """A pitch class's name ("F#"): the one speller for notes, chords and keys. Flats in a flat key ("Bb" in
    D minor), sharps otherwise."""
    flat = key is not None and parse(key) is not None and signature(key)[0] < 0
    return (FLATS if flat else NAMES)[k % 12]


def pitch_name(k: int, key: str | None = None) -> str:
    """"F#3"; spelled with flats in a flat key ("Bb4" in D minor), sharps otherwise."""
    return f"{pc_name(k, key)}{k // 12 - 1}"


def midis(p) -> list[int]:
    """The MIDI numbers a note plays (a chord is a list)."""
    return [midi(x) for x in p] if isinstance(p, list) else [midi(p)]


def parse(key: str) -> tuple[int, str] | None:
    """(tonic pitch class 0 … 11, mode) or None when `key` is not a key."""
    m = KEY.match(key.strip()) if isinstance(key, str) else None
    if m is None:
        return None
    pc = (TONICS[m.group(1).upper()] + {"#": 1, "b": -1}.get(m.group(2) or "", 0)) % 12
    return pc, m.group(3).lower()


def scale(key: str) -> list[int]:
    """The key's pitch classes, tonic first."""
    pc, mode = parse(key)
    return [(pc + s) % 12 for s in MODES[mode]]


def in_key(midi: int, key: str) -> bool:
    return midi % 12 in scale(key)


def snap(midi: int, key: str) -> int:
    """The nearest note of the key (ties go down)."""
    notes = scale(key)
    return min((midi + d for d in (0, -1, 1, -2, 2)), key=lambda k: (k % 12 not in notes, abs(k - midi), k))


def step_in_key(midi: int, key: str, sign: int) -> int:
    """The next note of the key above (sign > 0) or below `midi`; a pitch outside the key lands on the nearest one that way."""
    notes = scale(key)
    k = midi + (1 if sign > 0 else -1)
    while k % 12 not in notes and 0 <= k <= 127:
        k += 1 if sign > 0 else -1
    return k


def steps_in_key(midi: int, key: str, n: int) -> int:
    """`n` steps of the key up (n > 0) or down from `midi` (the first step from outside the key lands on the key)."""
    for _ in range(abs(n)):
        midi = step_in_key(midi, key, n)
    return midi


def signature(key: str) -> tuple[int, bool]:
    """(sharps, minor) for a MIDI key signature: sharps -7 … 7 (negative = flats). Modes use their major scale's."""
    pc, mode = parse(key)
    major_pc = (pc - MODE_DEGREE[mode]) % 12
    spelled = [n for n in SHARPS if parse(f"{SHARPS[n]} major")[0] == major_pc]   # F# / Gb: two spellings
    tonic = key.split()[0][1:]                                                   # "#", "b" or ""
    n = max(spelled) if "#" in tonic else min(spelled) if "b" in tonic else min(spelled, key=abs)
    return n, mode == "minor"


def from_signature(sharps: int, minor: bool) -> str:
    sharps = max(-7, min(7, sharps))
    return f"{(MINORS if minor else SHARPS)[sharps]} {'minor' if minor else 'major'}"


def key_for(root: dict, sec: float) -> str | None:
    """The key a note at `sec` is in: the key playing then, else (before the first key change) the first key; None
    while the song has no key."""
    return key_at(root, sec) or next((k["key"] for k in root.get("keys", []) if k.get("key")), None)


def key_at(root: dict, sec: float) -> str | None:
    """The key playing at `sec` seconds (the last key change at or before it), or None."""
    best, best_t = None, -1.0
    for k in root.get("keys", []):
        t = times.seconds(k.get("at", 0), root, k["id"])
        if best_t <= t <= sec + 1e-9:
            best, best_t = k.get("key"), t
    return best
