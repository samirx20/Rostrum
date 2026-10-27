"""Phones → mouth shapes, and the timing tools that make them read on screen.

Shapes (the classic 9, Preston Blair / Rhubarb Lip Sync names):
    X rest · A closed (M B P) · B slightly open, teeth together (most consonants, EE) · C open (EH AE IH, schwa)
    D wide open (AA, AY, AW) · E rounded (AO ER OY) · F puckered (OO OW W) · G teeth on lip (F V) · H tongue up (L)

    cues(phones, fps=24) -> [{"shape": "X", "start": 0.0, "end": 0.12}, {"shape": "B", …}, …]   (seconds in the file)
"""
from __future__ import annotations

import unicodedata

SHAPES = ("X", "A", "B", "C", "D", "E", "F", "G", "H")
TABLE = {
    "A": "m p b mʲ pʲ bʲ",
    "B": "t d k ɡ g s z ʃ ʒ tʃ dʒ θ ð n ŋ ɲ j h ɹ r ɾ ʔ ts x ç ɣ ʁ i iː ɪɹ ɨ",
    "C": "ɛ æ ə ɐ ʌ ɪ ᵻ e eː eɪ ɛɹ ɛː e̞",
    "D": "ɑː ɑ a aː aɪ aʊ ɑːɹ aɪɚ",
    "E": "ɔː ɔ ɜː ɜ ɚ ɔːɹ ɔɪ œ ø øː",
    "F": "uː u ʊ ʊɹ oʊ o oː w y yː ʉ ɯ ʍ",
    "G": "f v β ʋ",
    "H": "l ɭ ʎ ɫ əl",
}
SHAPE_OF = {p: s for s, ps in TABLE.items() for p in ps.split()}
VOWELS = {"a": "D", "ɑ": "D", "æ": "C", "e": "C", "ɛ": "C", "ə": "C", "ɐ": "C", "ʌ": "C", "i": "B", "ɪ": "C",
          "o": "F", "u": "F", "ʊ": "F", "y": "F", "ɔ": "E", "ɜ": "E", "œ": "E", "ø": "E"}
# A shape the target has no layer for shows the first of these it has (then their fallbacks, nearest first).
FALLBACK = {"X": ["A", "B"], "A": ["X", "B"], "B": ["C", "X"], "C": ["B", "D"], "D": ["C", "B"],
            "E": ["F", "C"], "F": ["E", "A"], "G": ["B", "A"], "H": ["B", "C"]}


def shape_of(phone: str) -> str:
    """A phone label's shape: the table, else the label without marks, else its first letter (vowels), else B."""
    if phone in SHAPE_OF:
        return SHAPE_OF[phone]
    bare = "".join(c for c in unicodedata.normalize("NFD", phone) if not unicodedata.combining(c))
    bare = bare.rstrip("ː0123456789.hʲ[") or bare
    return SHAPE_OF.get(bare) or VOWELS.get(bare[:1]) or "B"


def resolve(shape: str, have) -> str:
    """The shape actually shown when only the shapes in `have` have layers (nearest by FALLBACK, breadth first)."""
    seen, line = set(), [shape]
    while line:
        s = line.pop(0)
        if s in have:
            return s
        seen.add(s)
        line += [f for f in FALLBACK[s] if f not in seen and f not in line]
    raise ValueError(f"no mouth layer for {shape} or any shape near it; give at least one of {', '.join(SHAPES)}")


def cues(phones: list[dict], fps: float = 24, lead_frames: float = 1, min_frames: float = 1,
         rest_gap: float = 0.25, tail: float = 0.08, start: float | None = None, end: float | None = None,
         grid: float = 0.0) -> list[dict]:
    """Mouth cues over [start, end] (default: the phones' span), each starting on a frame (frames are 1/fps apart,
    one of them at `grid` s: the file time that lands on a comp frame):
    - a phone sounds at least `tail` s past where the model last hears it;
    - a silence shorter than `rest_gap` s holds the mouth before it; a longer one rests (X);
    - every shape starts `lead_frames` frames before its sound (mouths move ahead of what we hear);
    - a shape shorter than `min_frames` frames gives its time to the shape before it;
    - the last cue is always the rest (X), `tail` s after the last sound, even past the clip's end (a voice take cut
      right after its last word left the mouth open to the end of the scene: hand maker C, C10)."""
    lo = (phones[0]["start"] if phones else 0.0) if start is None else start
    hi = (phones[-1]["end"] + tail if phones else lo) if end is None else end
    raw, cursor = [["X", lo]], lo
    for p in phones:
        if p["start"] - cursor > rest_gap:
            raw.append(["X", cursor])
        raw.append([shape_of(p["phone"]), p["start"] - lead_frames / fps])
        cursor = max(cursor, p["end"] + tail)
    if hi - cursor > 1e-6:
        raw.append(["X", cursor])
    if hi <= lo:
        return [{"shape": "X", "start": lo, "end": lo}]
    snapped = [[s, max(lo, round((t - grid) * fps) / fps + grid)] for s, t in raw]
    out = _tidy(snapped, lo, hi, min_frames / fps - 1e-6)
    if phones and out[-1]["shape"] != "X":      # the mouth closes after the last sound, even when the clip ends on it
        t = max(round((cursor - grid) * fps) / fps + grid, out[-1]["start"] + 1 / fps)
        out[-1]["end"] = round(min(out[-1]["end"], t), 4)
        out.append({"shape": "X", "start": round(t, 4), "end": round(max(t, hi), 4)})
    return out


def _tidy(raw, lo, hi, shortest) -> list[dict]:
    out = []
    for i, (s, t) in enumerate(raw):
        nxt = raw[i + 1][1] if i + 1 < len(raw) else hi
        if nxt - t < shortest and out:                      # too short: the shape before keeps this time
            continue
        if out and out[-1]["shape"] == s:
            continue
        if out and t <= out[-1]["start"]:                   # starts no later than the one before: replaces it
            out[-1]["shape"] = s
            continue
        if out:
            out[-1]["end"] = round(t, 4)
        out.append({"shape": s, "start": round(t, 4), "end": round(hi, 4)})
    out[0]["start"] = round(lo, 4)
    merged = [out[0]]
    for c in out[1:]:
        if c["shape"] == merged[-1]["shape"]:
            merged[-1]["end"] = c["end"]
        else:
            merged.append(c)
    return merged
