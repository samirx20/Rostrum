"""Drum step patterns and fills, as a line of plain hits.

One string per drum, one character per 16th (16 = a bar of 4/4), each repeating over its own length:
    X accent    x hit    o ghost (soft)    r a 32nd-note roll on that step    t a triplet roll    . rest
Spaces and "|" are ignored, so "x..x ..x. ..x. ...." reads in beats.

Fills replace the last `beats` of every `every` bars:
    "snare"  a snare figure accenting into the downbeat (hats keep time)
    "toms"   a tom run down the `toms` (snare and hats rest)
    "roll"   a 32nd-note snare roll         "build"  quarters → 8ths → 16ths → roll        "stop"  everything rests
`crash=True` puts a cymbal on the downbeat after each fill; `last=False` leaves the final bars without one.
"""
from __future__ import annotations

from .pitch import refuse

VELS = {"X": 0.95, "x": 0.75, "o": 0.32, "r": 0.6, "t": 0.6}
FILLS = ("snare", "toms", "roll", "build", "stop")
KEEP_TIME = {"hat", "openHat", "shaker", "pedalHat"}


def _steps(voice: str, p, where: str) -> str:
    if isinstance(p, (list, tuple)):                 # step numbers in a bar of 16
        return "".join("x" if i in p else "." for i in range(16))
    s = str(p).replace(" ", "").replace("|", "")
    if not s or s.strip("Xxort."):
        refuse(where, f"{voice} {p!r}", "is one character per 16th: X accent, x hit, o ghost, r 32nd roll, t triplet roll, . rest",
               ['"x..x..x...x....."', "[0, 6, 10] (step numbers)"])
    return s


def _figure(kind: str, voice: str, n: int, toms) -> str | None:
    """A fill's `n` steps for one drum: None = plays as written, "" = rests."""
    def beats(f):
        k = -(-n // 4)
        return "".join(f(i, i == k - 1) for i in range(k))[-n:]
    if kind == "stop":
        return ""
    if kind == "snare":
        return beats(lambda i, last: "xxXX" if last else "x.xo") if voice == "snare" else None
    if kind == "roll":
        return beats(lambda i, last: "rrrX" if last else "rrrr") if voice == "snare" else ("" if voice in KEEP_TIME else None)
    if kind == "toms":
        return "" if voice == "snare" or voice in KEEP_TIME else None
    stages = ["x...", "x.x.", "xxxx", "rrrr"]               # build
    if voice == "snare":
        k = -(-n // 4)
        return beats(lambda i, last: stages[min(3, i * 4 // k)])[:-1] + "X"
    return "" if voice in KEEP_TIME else None


def drum_grid(patterns: dict, bars=1, fill=None, every=4, fill_beats=1, crash=False, last=True, toms=("tom",),
              beats_per_bar=4, where="drum_grid") -> list[dict]:
    """The hits of `patterns` ({"kick": "x...", "snare": "....x..."}) over `bars`, with an optional fill."""
    if not isinstance(patterns, dict) or not patterns:
        refuse(where, repr(patterns), 'is {drum: steps}', ['{"kick": "x..x..x...x.....", "snare": "....x.......x..."}'])
    if fill is not None and fill not in FILLS:
        refuse(where, f"fill {fill!r}", "is not a fill", [repr(f) for f in FILLS])
    per_bar = int(round(beats_per_bar * 4))
    total = bars * per_bar
    voices = {v: [p[i % len(p)] for i in range(total)] for v, p in ((v, _steps(v, p, where)) for v, p in patterns.items())}
    n = int(round(fill_beats * 4))
    if fill is not None:
        if not 0 < n <= every * per_bar:
            refuse(where, f"fill_beats={fill_beats!r}", f"is how many beats the fill lasts, at most the {every} bar(s) between fills")
        extra = ["snare"] if fill in ("snare", "roll", "build") else []
        for v in extra + (["cymbal"] if crash else []):
            voices.setdefault(v, ["."] * total)
        for end in range(every * per_bar, total + 1, every * per_bar):
            if not last and end >= total:
                break
            for v in list(voices):
                fig = _figure(fill, v, n, toms)
                if fig is not None:
                    voices[v][end - n:end] = list(fig) if fig else ["."] * n
            if fill == "toms":                              # the run walks down the toms given, high to low
                for i in range(n):
                    drum = toms[min(len(toms) - 1, i * len(toms) // n)]
                    voices.setdefault(drum, ["."] * total)[end - n + i] = "X" if i == n - 1 else "x"
            if crash and end < total:
                voices["cymbal"][end] = "X"
    out = []
    for v, steps in voices.items():
        for i, ch in enumerate(steps):
            at = i / 4
            if ch in "Xxo":
                out.append({"drum": v, "at": at, "vel": VELS[ch]})
            elif ch in "rt":
                k = 2 if ch == "r" else 3
                out += [{"drum": v, "at": at + j * 0.25 / k, "vel": round(VELS[ch] * (1 if j == 0 else 0.85), 3)} for j in range(k)]
    return sorted(out, key=lambda h: h["at"])
