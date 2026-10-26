"""Pitch facts the writing helpers share: chord symbols and Roman numerals as tones, a key's scale, steps in a key.

Note names and keys are the document's own (`doc/keys.py`): "F#3", "Bb2" (C4 = MIDI 60); keys "D minor", "Bb dorian".
A chord is a symbol ("Am7", "F#m7b5", "C/E", "Bbmaj9") or a numeral in the key ("vi", "V7/V", "bVII", "viiø7").
"""
from __future__ import annotations

import re

from rostrum_core import RostrumError, codes

from ..doc import keys as K

# Chord qualities as semitones above the root (an extension above the octave keeps its octave: 14 = the 9th).
QUALITIES = {
    "": (0, 4, 7), "maj": (0, 4, 7), "m": (0, 3, 7), "min": (0, 3, 7), "dim": (0, 3, 6), "aug": (0, 4, 8),
    "sus2": (0, 2, 7), "sus4": (0, 5, 7), "sus": (0, 5, 7), "5": (0, 7), "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9),
    "69": (0, 4, 7, 9, 14), "add9": (0, 4, 7, 14), "madd9": (0, 3, 7, 14),
    "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10), "mmaj7": (0, 3, 7, 11), "m7b5": (0, 3, 6, 10),
    "dim7": (0, 3, 6, 9), "aug7": (0, 4, 8, 10), "7sus4": (0, 5, 7, 10), "7b5": (0, 4, 6, 10),
    "9": (0, 4, 7, 10, 14), "maj9": (0, 4, 7, 11, 14), "m9": (0, 3, 7, 10, 14), "9sus4": (0, 5, 7, 10, 14),
    "7b9": (0, 4, 7, 10, 13), "7#9": (0, 4, 7, 10, 15), "7#11": (0, 4, 7, 10, 18), "maj7#11": (0, 4, 7, 11, 18),
    "7b13": (0, 4, 7, 10, 20), "11": (0, 7, 10, 14, 17), "m11": (0, 3, 7, 10, 14, 17),
    "13": (0, 4, 7, 10, 14, 21), "maj13": (0, 4, 7, 11, 14, 21), "m13": (0, 3, 7, 10, 14, 21),
}
ALIASES = {"M": "maj", "M7": "maj7", "Δ": "maj7", "Δ7": "maj7", "-": "m", "-7": "m7", "°": "dim", "o": "dim", "°7": "dim7",
           "o7": "dim7", "ø": "m7b5", "ø7": "m7b5", "+": "aug", "+7": "aug7", "mM7": "mmaj7", "mMaj7": "mmaj7"}
SYMBOL = re.compile(r"^([A-G])([#b]?)([^/]*)(?:/([A-G])([#b]?))?$")
NUMERAL = re.compile(r"^([b#]?)(VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)(°|o|ø|\+)?(.*)$")
DEGREES = ["I", "II", "III", "IV", "V", "VI", "VII"]
CHORD_FORMS = ['"Am"', '"Fmaj7"', '"G/B"', '"Dm9"', '"Bm7b5"', 'a numeral in the key: "vi", "V7", "bVII", "V7/V"']


def refuse(where: str, subject: str, problem: str, accepted=(), hint: str | None = None):
    raise RostrumError(codes.BAD_ARGUMENT, where, subject, problem, accepted, hint)


def midi(pitch, where: str) -> int:
    """A note name ("A3", "Bb2") or MIDI number as MIDI, or a loud error naming the call."""
    try:
        return K.midi(pitch)
    except (ValueError, TypeError, KeyError):
        refuse(where, repr(pitch), "is not a note name", ['"A3"', '"F#2"', '"Bb4"', "60 (a MIDI number)"])


def name(m: int, key: str | None = None) -> str:
    """A MIDI number as a note name, flats in a flat key ("Bb4" in D minor)."""
    return K.pitch_name(int(m), key if key and K.parse(key) else None)


def scale(key: str | None, where: str) -> list[int]:
    """The key's pitch classes, tonic first (C major's when there is no key)."""
    if key is None:
        return list(K.MODES["major"])
    if K.parse(key) is None:
        refuse(where, f"key {key!r}", "is not a key", K.FORMS)
    return K.scale(key)


def scale_step(m: int, steps: int, pcs: list[int]) -> int:
    """`m` moved by `steps` notes of the scale (a note outside it first drops to the scale note below)."""
    while m % 12 not in pcs:
        m -= 1
    for _ in range(abs(int(steps))):
        m += 1 if steps > 0 else -1
        while m % 12 not in pcs:
            m += 1 if steps > 0 else -1
    return m


def outside_key(ln: list[dict], key: str | None) -> list[str]:
    """The distinct pitch names in a line that are not notes of `key` (none when there is no key). The one check every
    line helper's reply uses, so a note out of the key is always said, never found later."""
    if key is None or K.parse(key) is None:
        return []
    pcs = K.scale(key)
    bad = {m for n in ln if "pitch" in n for m in K.midis(n["pitch"]) if m % 12 not in pcs}
    return [name(m, key) for m in sorted(bad)]


def _pc(letter: str, acc: str) -> int:
    return (K.TONICS[letter] + {"#": 1, "b": -1}.get(acc, 0)) % 12


def roman(numeral: str, key: str | None, where: str = "roman") -> str:
    """A Roman numeral in `key` as a chord symbol: the degree of the key's own scale ("VII" in A minor is G); b / #
    alter it ("bVII" in C major is Bb); upper case major, lower case minor, ° dim, ø half-dim, + aug; a suffix as in a
    symbol ("V7", "ii7", "IVmaj7", "Vsus4"); "/" a secondary chord ("V7/V" in C is D7). A symbol comes back as written."""
    head, _, target = numeral.strip().partition("/")
    m = NUMERAL.match(head)
    if not m or SYMBOL.match(numeral.strip()):
        return numeral
    if key is None:
        refuse(where, f"numeral {numeral!r}", "needs the song's key", ['key("D minor") at the top of the script', 'key="D minor" here'])
    pcs = scale(key, where)
    if target:
        t = NUMERAL.match(target)
        if not t:
            return numeral                                  # "V/B" would be a bass note, not a numeral chord
        tonic = (pcs[DEGREES.index(t[2].upper())] + {"b": -1, "#": 1}.get(t[1], 0)) % 12
        pcs = [(tonic + s) % 12 for s in K.MODES["major"]]
    acc, deg, mark, sfx = m[1], m[2], m[3] or "", m[4].strip()
    pc = (pcs[DEGREES.index(deg.upper())] + {"b": -1, "#": 1}.get(acc, 0)) % 12
    minor = deg == deg.lower()
    if mark in ("°", "o"):
        quality = "dim7" if sfx == "7" else "dim" + sfx
    elif mark == "ø":
        quality = "m7b5"
    elif mark == "+":
        quality = "aug7" if sfx == "7" else "aug"
    elif re.match(r"^(sus|add|maj|5)", sfx):
        quality = ("m" + sfx) if minor and re.match(r"^(add|maj)", sfx) else sfx
    else:
        quality = ("m" if minor else "") + sfx
    flat = acc == "b" or (acc != "#" and key is not None and K.signature(key)[0] < 0)
    symbol = (K.FLATS if flat else K.NAMES)[pc] + quality
    tones(symbol, where)                                    # a numeral that makes no known chord fails here
    return symbol


def tones(chord: str, where: str, key: str | None = None) -> dict:
    """{"symbol", "root", "bass", "pcs" (root first), "third", "fifth", "seventh"} of a chord symbol or numeral."""
    symbol = roman(chord, key, where) if isinstance(chord, str) else chord
    m = SYMBOL.match(symbol.strip()) if isinstance(symbol, str) else None
    quality = m and ALIASES.get(m[3], m[3])
    if not m or quality not in QUALITIES:
        refuse(where, repr(chord), "is not a chord symbol this knows", CHORD_FORMS,
               f"Qualities: {', '.join(q or '(major)' for q in QUALITIES)}.")
    root = _pc(m[1], m[2])
    ivs = QUALITIES[quality]
    pcs = list(dict.fromkeys((root + i) % 12 for i in ivs))

    def has(*options):
        return next(((root + i) % 12 for i in options if i in {x % 12 for x in ivs}), None)
    return {"symbol": symbol, "root": root, "bass": _pc(m[4], m[5]) if m[4] else root, "pcs": pcs,
            "third": has(4, 3, 5, 2), "fifth": has(7, 6, 8), "seventh": has(10, 11, 9) if len(ivs) > 3 else None}
