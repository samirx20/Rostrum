"""Pure music theory for the ears: note names and cents, intervals, chord naming (from note sets and from chroma),
key estimates and the low-interval limits. Numbers in, names out; no audio, no document."""
from __future__ import annotations

import math

import numpy as np

from ..doc.keys import NAMES, from_signature, parse, pc_name, pitch_name, signature

# Chord shapes as semitones above the root, most specific first (a tie goes to the earlier one).
SHAPES = [("maj7", (0, 4, 7, 11)), ("m7", (0, 3, 7, 10)), ("7", (0, 4, 7, 10)), ("m7b5", (0, 3, 6, 10)),
          ("dim7", (0, 3, 6, 9)), ("", (0, 4, 7)), ("m", (0, 3, 7)), ("dim", (0, 3, 6)), ("aug", (0, 4, 8)),
          ("sus4", (0, 5, 7)), ("sus2", (0, 2, 7)), ("5", (0, 7))]
INTERVALS = ["unison", "minor 2nd", "major 2nd", "minor 3rd", "major 3rd", "perfect 4th", "tritone", "perfect 5th",
             "minor 6th", "major 6th", "minor 7th", "major 7th", "octave"]
# Lowest note (MIDI) a simultaneous interval of that many semitones stays clear below (a common orchestration
# chart, simplified: close intervals turn to mud low down). Wider than 7 semitones: no limit.
LOW_LIMIT = {1: 57, 2: 52, 3: 43, 4: 40, 5: 36, 6: 36, 7: 28}
# Krumhansl-Kessler key profiles (tonic first).
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def hz_to_midi(f):
    return 69 + 12 * np.log2(np.asarray(f, dtype=float) / 440.0)


def midi_to_note(m: float) -> tuple[str, float]:
    """("A4", cents) for a fractional MIDI number: the nearest note and how many cents above (+) or below it."""
    k = int(round(m))
    return pitch_name(k), round((m - k) * 100, 1)


def interval_name(semitones: int) -> str:
    s = abs(int(semitones))
    return INTERVALS[s] if s <= 12 else f"{INTERVALS[s % 12]} + {s // 12} octave{'s' if s >= 24 else ''}"


def key_name(tonic: int, mode: str) -> str:
    """A major or minor key by its usual spelling: "Bb major", "G# minor" (the signature with fewer accidentals)."""
    return from_signature(signature(f"{NAMES[tonic]} {mode}")[0], mode == "minor")


def name_chord(midis, bass: int | None = None, key: str | None = None) -> str | None:
    """A chord's name from the MIDI notes sounding ("Am7", "C/E", "G5"), spelled in `key` ("Bb" in D minor), None
    when it is not a chord (one note, or a cluster no shape fits). The root is the one whose shape fits with the
    fewest notes over or missing."""
    pcs = sorted({int(m) % 12 for m in midis})
    if len(pcs) < 2:
        return None
    bass_pc = (min(midis) if bass is None else bass) % 12
    best = None
    for root in pcs:
        rel = {(p - root) % 12 for p in pcs}
        for order, (suffix, shape) in enumerate(SHAPES):
            miss = len(set(shape) - rel)
            extra = len(rel - set(shape))
            cost = miss * 2 + extra
            if miss > 1 or cost > 2 or len(rel) < 2:
                continue
            rank = (cost, root != bass_pc, order)
            if best is None or rank < best[0]:
                best = (rank, root, suffix)
    if best is None:
        return None
    _, root, suffix = best
    name = pc_name(root, key) + suffix
    return name if root == bass_pc else f"{name}/{pc_name(bass_pc, key)}"


def _chroma_templates():
    out = []
    for root in range(12):
        for suffix, shape in SHAPES[:7] + SHAPES[8:9]:
            if suffix in ("dim7", "m7b5"):
                continue
            v = np.zeros(12)
            v[[(root + s) % 12 for s in shape]] = 1.0
            out.append((root, suffix, v / np.linalg.norm(v)))
    return out


_TEMPLATES = _chroma_templates()


def chord_from_chroma(c, silent: float = 1e-3, key: str | None = None) -> tuple[str, float]:
    """(name spelled in `key`, confidence 0 … 1) of the chord a 12-bin chroma vector looks most like; ("N", 0) when
    it is silent."""
    c = np.asarray(c, dtype=float)
    if c.max() < silent:
        return "N", 0.0
    c = c / np.linalg.norm(c)
    s, root, suffix = max((float(c @ t), root, suffix) for root, suffix, t in _TEMPLATES)
    return pc_name(root, key) + suffix, round(s, 3)


def estimate_key(weights, top: int = 3) -> dict:
    """The keys a 12-bin pitch-class weight vector fits best (major / minor, Krumhansl profiles): {"key", "margin"
    (best correlation minus the runner-up's), "ranked": [(key, correlation)]}. A flat or empty vector is "unknown"."""
    w = np.asarray(weights, dtype=float)
    if w.sum() <= 0 or np.ptp(w) <= 0:
        return {"key": None, "margin": 0.0, "ranked": []}
    ranked = []
    for mode, prof in (("major", MAJOR), ("minor", MINOR)):
        for tonic in range(12):
            r = float(np.corrcoef(w, np.roll(prof, tonic))[0, 1])
            ranked.append((key_name(tonic, mode), round(r, 3)))
    ranked.sort(key=lambda kv: -kv[1])
    return {"key": ranked[0][0], "margin": round(ranked[0][1] - ranked[1][1], 3), "ranked": ranked[:top]}


def relative_pair(a: str, b: str) -> bool:
    """True when two keys share their notes (C major and A minor): an estimate can't tell them apart without a bass."""
    pa, pb = parse(a), parse(b)
    if pa is None or pb is None or pa[1] == pb[1]:
        return False
    major, minor = (pa, pb) if pa[1] == "major" else (pb, pa)
    return (major[0] - minor[0]) % 12 == 3


def low_interval_limit(semitones: int) -> int | None:
    return LOW_LIMIT.get(abs(int(semitones)))


def cents(a_midi: float, b_midi: float) -> float:
    return round((a_midi - b_midi) * 100, 1)


def finite(x) -> bool:
    return x is not None and not math.isnan(x)
