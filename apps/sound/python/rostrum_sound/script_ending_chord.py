"""The last chord an `ending(...)` lands on (script_ending.py), voiced from where each part already is.

The chord is the home key's tonic triad ("i" in a minor-third mode, else "I"), a numeral or symbol (`chord="V"`,
`chord="Gsus4"`), or its tones as pitches (`chord=["D3", "F3", "A3"]`, the lowest is the root). Each part moves from
its last notes to the nearest chord tones, so it stays in its own register and range: a single-note part takes the
nearest tone (the lowest part the nearest root, so the chord stands on its root), a part playing chords takes as many
voices as its last chord had, each moved to the nearest tone, doubled tones moved to a tone still missing.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from .doc import keys as K
from .writing.pitch import name, tones

FORMS = ['ending("ring") (the home chord of key(...))', 'chord="V"', 'chord="Gsus4"', 'chord=["D3", "F3", "A3"]']


def home(key: str) -> str:
    """The home chord's numeral in `key`: minor when the mode's third is minor."""
    sc = K.scale(key)
    return "i" if (sc[2] - sc[0]) % 12 == 3 else "I"


def pitch_classes(chord, key, where) -> tuple[list[int], int]:
    """(the chord's pitch classes, root first; the root's pitch class)."""
    if isinstance(chord, (list, tuple)):
        try:
            ms = sorted(K.midi(p) for p in chord)
        except Exception:
            raise RostrumError(codes.BAD_ARGUMENT, where, f"chord={chord!r}", "is not a list of pitches", FORMS) from None
        if not ms:
            raise RostrumError(codes.BAD_ARGUMENT, where, "chord=[]", "has no pitches", FORMS)
        pcs = list(dict.fromkeys(m % 12 for m in ms))
        return pcs, pcs[0]
    if chord is None and key is None:
        raise RostrumError(codes.BAD_ARGUMENT, where, "the last chord", "needs the song's key to find home",
                           ['key("D minor") in the script', *FORMS[2:]])
    t = tones(home(key) if chord is None else chord, where, key)
    return t["pcs"], t["root"]


def _nearest(m: int, pcs, prefer_down=True) -> int:
    best = None
    for d in range(0, 7):
        for c in ((m - d, m + d) if prefer_down else (m + d, m - d)):
            if c % 12 in pcs:
                best = c if best is None else best
        if best is not None:
            return best
    return m


def land(last: list[int], pcs: list[int], root: int, lowest_part: bool) -> list[int]:
    """The notes a part ends on, from the notes it played last (MIDI, low to high)."""
    if len(last) == 1:
        return [_nearest(last[0], [root] if lowest_part else pcs)]
    out = []
    for i, m in enumerate(sorted(last)):
        n = _nearest(m, [root] if lowest_part and i == 0 else pcs)
        while n in out:
            n += 12
        out.append(n)
    missing = [p for p in pcs if p not in {n % 12 for n in out}]
    for p in missing[:max(0, len(out) - len({n % 12 for n in out}))]:
        seen, k = set(), None
        for i, n in enumerate(out):             # a doubled tone (not the bass) moves to the missing one
            if n % 12 in seen and i > 0:
                k = i
            seen.add(n % 12)
        if k is None:
            break
        cand = _nearest(out[k], [p])
        if cand not in out:
            out[k] = cand
    return sorted(out)


def names(ms: list[int], key) -> list[str] | str:
    got = [name(m, key) for m in ms]
    return got[0] if len(got) == 1 else got
