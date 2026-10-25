"""Written chord voicings: each chord becomes the note names it plays, decided when the script runs.

    "close"   the tones stacked as tightly as they go, from the inversion's tone up
    "drop2" | "drop3" | "drop24"   close, then the 2nd (3rd; 2nd and 4th) voice from the top down an octave
    "spread"  close, then every other voice from the bottom up an octave (root, fifth, tenth …)
    "shell"   root, third and seventh (or sixth; else fifth) only
    "led"     each chord takes the voicing that moves least from the one before (shared tones held, the rest by
              step), inside `range`, optionally keeping `top` as the top note

`voices` sets how many tones (the fifth goes first, then the root; the root, then the fifth is doubled when the chord
has fewer); `rootless` leaves the root to the bass; `bass` adds the chord's bass note (the slash note, else the root)
an octave or more under the voicing. The same chords always give the same notes.
"""
from __future__ import annotations

from .pitch import midi, name, refuse, tones

VOICINGS = ("led", "close", "drop2", "drop3", "drop24", "spread", "shell")
LOW_CLUSTER = 60                 # under C4 two voices closer than a minor 3rd are left out of the "led" search


def _first(*pcs):
    return next(p for p in pcs if p is not None)


def _pick(t: dict, voicing: str, voices, rootless: bool, double_from: int = 0) -> list[int]:
    """The pitch classes to voice."""
    if voicing == "shell":                       # (pitch class 0 is C: "is not None", never "or")
        sixth = (t["root"] + 9) % 12
        return [t["root"], _first(t["third"], t["fifth"], t["root"]),
                _first(t["seventh"], sixth if sixth in t["pcs"] else None, t["fifth"], t["root"])]
    pcs = [p for p in t["pcs"] if not (rootless and len(t["pcs"]) >= 3 and p == t["root"])]
    n = voices or max(3, min(4, len(pcs)))
    for drop in (t["fifth"], None if rootless else t["root"]):
        if len(pcs) > n and drop in pcs:
            pcs.remove(drop)
    pcs = pcs[:n]
    doubles = [t["third"] if rootless else t["root"], t["fifth"], t["third"]]
    doubles = [d if d is not None else t["root"] for d in doubles]
    i = double_from
    while len(pcs) < n:
        pcs.append(doubles[i % 3])
        i += 1
    return pcs


def _close(pcs: list[int], inversion: int, lo: int) -> list[int]:
    k = inversion % len(pcs)
    out: list[int] = []
    for pc in pcs[k:] + pcs[:k]:
        m = out[-1] + 1 if out else lo
        while (m - pc) % 12:
            m += 1
        out.append(m)
    return out


def _candidates(pcs: list[int], lo: int, hi: int) -> list[list[int]]:
    """Every voicing of the tones inside lo … hi: one note per tone, no unisons, no close intervals low down."""
    out = []

    def walk(i, chosen):
        if i == len(pcs):
            s = sorted(chosen)
            if all(b > a and (a >= LOW_CLUSTER or b - a >= 3) for a, b in zip(s, s[1:])):
                out.append(s)
            return
        for m in range(lo, hi + 1):
            if (m - pcs[i]) % 12 == 0 and m not in chosen:
                walk(i + 1, chosen + [m])
    walk(0, [])
    return out


def _motion(prev: list[int], nxt: list[int]) -> float:
    """How far the voices move: each new note to its nearest old one, plus half the top voice's move."""
    return sum(min(abs(p - m) for p in prev) for m in nxt) + 0.5 * abs(prev[-1] - nxt[-1])


def voice(chords, key=None, voicing="led", inversion=0, voices=None, range=("G3", "D5"), rootless=False, top=None,
          bass=False, where="voice") -> list[list[str]]:
    """The note names of each chord (low to high): voice(["Am", "F", "C", "G"]) or numerals in the key."""
    if isinstance(chords, str):
        chords = [chords]
    if voicing not in VOICINGS:
        refuse(where, f"voicing {voicing!r}", "is not a voicing", [repr(v) for v in VOICINGS])
    lo, hi = midi(range[0], f"{where} range"), midi(range[1], f"{where} range")
    if hi - lo < 12:
        refuse(where, f"range {tuple(range)!r}", "is low and high at least an octave apart", ['("G3", "D5")'])
    if voices is not None and not (isinstance(voices, int) and 2 <= voices <= 6):
        refuse(where, f"voices={voices!r}", "is how many tones, 2 … 6")
    if not (isinstance(inversion, int) and 0 <= inversion <= 5):
        refuse(where, f"inversion={inversion!r}", "is 0 (root position), 1 (first), 2 (second), 3 (third)")
    top_m = midi(top, f"{where} top") if top is not None else None
    centre = lo + (hi - lo) * 0.42
    prev, out = None, []
    for c in chords:
        t = tones(c, where, key)
        if voicing == "led":
            pcs = _pick(t, voicing, voices, rootless)
            cands = _candidates(pcs, lo, hi)
            for d in (1, 2):
                if not cands:
                    pcs = _pick(t, voicing, voices, rootless, d)
                    cands = _candidates(pcs, lo, hi)
            if not cands:
                refuse(where, repr(c), f"does not fit {len(pcs)} voices in {range[0]}–{range[1]}",
                       ["a wider range", "fewer voices"])

            def cost(v):
                start = _motion(prev, v) if prev else 0.2 * (v[-1] - v[0])
                return start + 0.15 * abs(sum(v) / len(v) - centre) - (4 if top_m is not None and v[-1] == top_m else 0)
            notes = min(cands, key=cost)
        else:
            notes = _close(_pick(t, voicing, voices, rootless), inversion, lo)
            drops = {"drop2": [1], "drop3": [2], "drop24": [1, 3]}.get(voicing, [])
            for k in drops:
                if len(notes) - 1 - k >= 0:
                    notes[len(notes) - 1 - k] -= 12
            if voicing == "spread":
                notes = [m + 12 if i % 2 else m for i, m in enumerate(notes)]
            notes.sort()
            if notes[0] < lo - 12:
                notes = [m + 12 for m in notes]
        prev = notes
        if bass:
            b = notes[0] - 12
            while (b - t["bass"]) % 12:
                b -= 1
            notes = [b, *notes]
        out.append([name(m, key) for m in notes])
    return out
