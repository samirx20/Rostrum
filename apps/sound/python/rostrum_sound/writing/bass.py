"""Bass lines from a progression. Each bar plays a pattern of 16ths whose characters are chord degrees, so one
pattern follows every chord:

    R root (the slash note on "C/E")    r the root as a ghost (soft)    8 the root an octave up
    5 fifth    3 third    7 seventh (the octave where the chord has none)    b the fifth below the root
    A an approach: a step of the key into the next chord's root (from below when the line is under it); a half
      step with `chromatic=True`
    - holds the note before    . rest

Named styles are the common bass motions (STYLES); any other motion is a pattern. `approach=True` turns the last
note before each change into an approach note; `push` anticipates each change; `octave` places the roots
(1: E1–D#2, 2: E2–D#3); `gate` shortens every note.
"""
from __future__ import annotations

from .line import grid
from .pitch import name, refuse, scale, scale_step, tones

STYLES = {
    "root": "R---------------",          # one note a bar
    "half": "R-------R-------",          # two a bar
    "pulse": "R-R-R-R-R-R-R-R-",         # 8ths on the root
    "octave": "R-8-R-8-R-8-R-8-",        # root and octave
    "rootFifth": "R-------5-------",     # root, then fifth
    "walking": "R---3---5---A---",       # quarters up the chord into an approach note
    "syncopated": "R--r..8-R-.r5-8r",    # off-beat pushes and ghost notes
}
DEGREES = "Rr8537bA"


def bass_line(chords, key=None, style="root", pattern=None, per=4, approach=False, push=0.0, octave=1, gate=0.9,
              vel=0.85, beats_per_bar=4, chromatic=False, where="bass_line") -> list[dict]:
    """A bass line over the progression (each chord `per` beats), as a line of notes. Approach notes ("A") are a step
    of the song's key; `chromatic=True` makes them half steps, which can leave the key (the reply then names them)."""
    if isinstance(chords, str):
        chords = [chords]
    if pattern is None and style not in STYLES:
        refuse(where, f"style {style!r}", "is not a bass style", [*map(repr, STYLES), 'pattern="R--r..8-R-.r5-8r"'])
    pat = pattern if pattern is not None else STYLES[style]
    if not (isinstance(octave, int) and 0 <= octave <= 3) or not 0 < gate <= 1:
        refuse(where, f"octave={octave!r}, gate={gate!r}", "are 0 … 3 (where the roots sit: 1 = E1–D#2) and 0 … 1")
    ts = [tones(c, where, key) for c in chords]
    if not 0 <= push < per:
        refuse(where, f"push={push!r}", f"is beats each change comes early, under one chord's {per:g} beats")
    total = per * len(ts)
    low = 12 * (octave + 1) + 4                           # E of the octave: roots sit from here up to D#
    pcs = scale(key, where) if key else None

    def approach_note(target, from_below):
        """The note leading into `target`: a step of the key (so the line stays in it), or a half step when asked."""
        if chromatic or pcs is None:
            return target - 1 if from_below else target + 1
        return scale_step(target, -1 if from_below else 1, pcs)

    def root_of(t):
        return low + (t["bass"] - low) % 12

    def chord_at(beat):
        return min(len(ts) - 1, int((beat + push) / per + 1e-9))
    hits = [list(h) for h in grid(pat, int(round(total * 4)), DEGREES, where)]
    if approach:
        for i in range(len(hits) - 1):
            if chord_at(hits[i + 1][0]) != chord_at(hits[i][0]):
                hits[i][2] = "A"
    out, prev = [], root_of(ts[0])
    for at, ln, ch in hits:
        i = chord_at(at)
        t, root = ts[i], root_of(ts[i])

        def deg(pc, fallback):
            return root + fallback if pc is None else root + (pc - t["bass"]) % 12
        target = root_of(ts[min(len(ts) - 1, i + 1)])
        m = {"8": root + 12, "5": deg(t["fifth"], 7), "b": deg(t["fifth"], 7) - 12, "3": deg(t["third"], 4),
             "7": root + 12 if t["seventh"] is None else deg(t["seventh"], 10),
             "A": approach_note(target, prev < target)}.get(ch, root)
        prev = m
        strong = 1.0 if at % beats_per_bar == 0 else 0.9 if at % 1 == 0 else 0.8 if at % 0.5 == 0 else 0.72
        out.append({"pitch": name(m, key), "at": at, "dur": ln * gate, "vel": round(0.5 * vel if ch == "r" else vel * strong, 3)})
    return out
