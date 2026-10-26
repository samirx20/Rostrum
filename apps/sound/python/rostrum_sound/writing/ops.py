"""Note operations and development: a composer's variation tools and a DAW's MIDI tools, on a line.

    vary(line, "steps:1+displace:0.5")        one or more ops, joined with "+", left to right
    develop(line, repeat=4, vary=["same", "steps:1", "same", "end:-1"])   the line n times, each repeat its own ops

Ops are "name" or "name:arg". Work is in beats from the line's start; scale steps use the key. The span (for
retrograde, displace, dynamics, repeats) is `every`, else the line rounded up to whole bars.
"""
from __future__ import annotations

from .line import span as line_span
from .pitch import midi, name, refuse, scale, scale_step

ACCENT = {"X": 1.2, "x": 1.0, "o": 0.55, ".": 0.85}


class _Ctx(dict):
    """Only for reading fields as attributes inside this module (scripts never see it)."""
    __getattr__ = dict.__getitem__


UNITS = {"octave": "octaves", "steps": "scale steps", "thin": "beats", "displace": "beats", "augment": "times as long"}


def _num(arg, default, lo, hi, op, c):
    x = default if arg in (None, "") else _float(arg, op, c)
    if not lo <= x <= hi:
        unit = f" {UNITS[op]}" if op in UNITS else ""
        refuse(c.where, f'"{op}:{arg}"', f"takes a number of{unit} from {lo:g} to {hi:g}" if unit else f"takes a number {lo:g} … {hi:g}",
               [f"{op}:{n:g}" for n in sorted({lo, default, hi})])
    return x


def _float(arg, op, c):
    try:
        return float(arg)
    except ValueError:
        refuse(c.where, f'"{op}:{arg}"', "takes a number")


def _pitches(ns, f, c, op):
    def one(p, n, i):
        return name(f(midi(p, f"{c.where} {op}"), n, i), c.key)
    return [{**n, "pitch": [one(p, n, i) for p in n["pitch"]] if isinstance(n["pitch"], list) else one(n["pitch"], n, i)}
            if "pitch" in n else n for i, n in enumerate(ns)]


def _vel(n, f):
    return {**n, "vel": round(min(1.0, max(0.02, (n.get("vel") if n.get("vel") is not None else 0.7) * f)), 3)}


def _invert(ns, a, c):
    first = next((n["pitch"] for n in ns if "pitch" in n), None)
    if first is None:
        return ns
    axis = midi(a if a else (first[0] if isinstance(first, list) else first), f"{c.where} invert")

    def degree(m):
        d, x = 0, axis
        while x < m:
            x, d = scale_step(x, 1, c.pcs), d + 1
        while x > m:
            x, d = scale_step(x, -1, c.pcs), d - 1
        return d
    return _pitches(ns, lambda m, n, i: scale_step(axis, -degree(m), c.pcs), c, "invert")


def _thin(ns, a, c):
    g = _num(a, 1, 0.125, 16, "thin", c)
    kept = [n for i, n in enumerate(ns) if i == 0 or abs(n["at"] / g - round(n["at"] / g)) < 1e-6]
    return [{**n, "dur": max(n.get("dur", 0), (kept[i + 1]["at"] if i + 1 < len(kept) else min(c.span, n["at"] + g)) - n["at"])}
            for i, n in enumerate(kept)]


def _thicken(ns, a, c):
    out = []
    for i, n in enumerate(ns):
        nxt = ns[i + 1] if i + 1 < len(ns) else None
        if not nxt or n.get("dur", 0) < 0.5 or isinstance(n.get("pitch"), list) or isinstance(nxt.get("pitch"), list) or "pitch" not in n:
            out.append(n)
            continue
        m, to = midi(n["pitch"], c.where), midi(nxt["pitch"], c.where)
        if abs(to - m) < 3:
            out.append(n)
            continue
        half = n["dur"] / 2                          # a passing tone: the second half steps toward the next note
        out += [{**n, "dur": half}, _vel({**n, "at": n["at"] + half, "dur": half,
                                          "pitch": name(scale_step(m, 1 if to > m else -1, c.pcs), c.key)}, 0.85)]
    return out


def _legato(ns, a, c):
    o = _num(a, 0.02, 0, 1, "legato", c)
    out = []
    for i, n in enumerate(ns):
        nxt = next((x["at"] for x in ns[i + 1:] if x["at"] > n["at"] + 1e-6), None)
        out.append({**n, "dur": nxt - n["at"] + o if nxt is not None else max(n.get("dur", 0), c.span - n["at"])})
    return out


def _accent(ns, a, c):
    if not a or a.strip("Xxo."):
        refuse(c.where, f'"accent:{a}"', "is one character per 16th, cycling: X accent, x as written, o ghost, . a little softer",
               ['"accent:X..xo.x."'])
    return [_vel(n, ACCENT[a[round(n["at"] * 4) % len(a)]]) for n in ns]


def _dynamics(ns, a, c):
    parts = (a or "").split(">")
    if len(parts) != 2:
        refuse(c.where, f'"dynamics:{a}"', "scales velocity from one factor to another across the line", ['"dynamics:0.6>1.1" (a crescendo)'])
    lo, hi = (_float(p, "dynamics", c) for p in parts)
    return [_vel(n, lo + (hi - lo) * (n["at"] / c.span if c.span else 0)) for n in ns]


def _fit(ns, a, c):
    lo, hi = (midi(p, f"{c.where} fit") for p in (a or ":").split(":")[:2])
    if hi - lo < 11:
        refuse(c.where, f'"fit:{a}"', "folds the notes into a register at least an octave wide", ['"fit:C3:C5"'])

    def fold(m, n, i):
        while m < lo:
            m += 12
        while m > hi:
            m -= 12
        return m
    return _pitches(ns, fold, c, "fit")


def _ratchet(ns, a, c):
    k = int(_num(a, 2, 2, 8, "ratchet", c))
    return [_vel({**n, "at": n["at"] + j * n.get("dur", 0.25) / k, "dur": n.get("dur", 0.25) / k * 0.9}, 0.8 if j else 1)
            for n in ns for j in range(k)]


OPS = {
    "same": lambda ns, a, c: ns,
    "rest": lambda ns, a, c: [],
    "transpose": lambda ns, a, c: _pitches(ns, lambda m, n, i: m + int(_num(a, 0, -48, 48, "transpose", c)), c, "transpose"),
    "octave": lambda ns, a, c: _pitches(ns, lambda m, n, i: m + 12 * int(_num(a, 1, -4, 4, "octave", c)), c, "octave"),
    "steps": lambda ns, a, c: _pitches(ns, lambda m, n, i: scale_step(m, int(_num(a, 1, -14, 14, "steps", c)), c.pcs), c, "steps"),
    "invert": _invert,
    "retrograde": lambda ns, a, c: [{**n, "at": c.span - n["at"] - n.get("dur", 0)} for n in ns],
    "reversePitches": lambda ns, a, c: [{**n, "pitch": ns[len(ns) - 1 - i].get("pitch", n.get("pitch"))} for i, n in enumerate(ns)],
    "displace": lambda ns, a, c: [{**n, "at": (n["at"] + _num(a, 0.5, -64, 64, "displace", c)) % c.span} for n in ns],
    "augment": lambda ns, a, c: (lambda f: [{**n, "at": n["at"] * f, "dur": n.get("dur", 0) * f} for n in ns])(_num(a, 2, 0.1, 8, "augment", c)),
    "diminish": lambda ns, a, c: (lambda f: [{**n, "at": n["at"] / f, "dur": n.get("dur", 0) / f} for n in ns])(_num(a, 2, 0.1, 8, "diminish", c)),
    "thin": _thin,
    "thicken": _thicken,
    "double": lambda ns, a, c: ns + [_vel(x, 0.8) for x in _pitches(ns, lambda m, n, i: m + int(_num(a, 12, -36, 36, "double", c)), c, "double")],
    "quantize": lambda ns, a, c: (lambda g: [{**n, "at": round(n["at"] / g) * g, "dur": max(g / 2, round(n.get("dur", g) / g) * g or g)} for n in ns])(_num(a, 0.25, 1 / 32, 4, "quantize", c)),
    "accent": _accent,
    "dynamics": _dynamics,
    "gate": lambda ns, a, c: [{**n, "dur": n.get("dur", 0) * _num(a, 0.5, 0.05, 2, "gate", c)} for n in ns],
    "legato": _legato,
    "staccato": lambda ns, a, c: [{**n, "dur": min(n.get("dur", 0.25), 0.25) * 0.6} for n in ns],
    "velocity": lambda ns, a, c: [{**n, "vel": _num(a, 0.7, 0.02, 1, "velocity", c)} for n in ns],
    "ratchet": _ratchet,
    "fit": _fit,
    "cut": lambda ns, a, c: (lambda at: [{**n, "dur": min(n.get("dur", 0), at - n["at"])} for n in ns if n["at"] < at - 1e-6])(_num(a, c.span, 0, 1024, "cut", c)),
    "end": lambda ns, a, c: ns[:-1] + _pitches(ns[-1:], lambda m, n, i: scale_step(m, int(_num(a, -1, -14, 14, "end", c)), c.pcs), c, "end"),
}


def _apply(ns, ops, c):
    out = sorted(ns, key=lambda n: n["at"])
    for part in [p.strip() for p in (ops or "same").split("+") if p.strip()]:
        op, _, arg = part.partition(":")
        if op not in OPS:
            refuse(c.where, f'op "{op}"', "is not a note op", list(OPS), 'Join ops with "+": "thin+octave:1".')
        out = sorted(OPS[op](out, arg or None, c), key=lambda n: n["at"])
    return out


def vary(ln, ops, key=None, every=None, beats_per_bar=4, where="vary") -> list[dict]:
    """The line with `ops` applied ("steps:2", "invert+octave:-1", "accent:X..x")."""
    c = _Ctx(key=key, pcs=scale(key, where), where=where, span=line_span(ln, beats_per_bar, every))
    return _apply(ln, ops, c)


def develop(ln, repeat=2, vary=None, every=None, key=None, beats_per_bar=4, where="develop") -> list[dict]:
    """The line `repeat` times, each `every` beats after the last (default: the line rounded up to bars); repeat k gets
    vary[k % len(vary)] ("same" keeps it as written)."""
    if not (isinstance(repeat, int) and 1 <= repeat <= 256):
        refuse(where, f"repeat={repeat!r}", "is how many times the line plays, 1 … 256")
    if vary is not None and (isinstance(vary, str) or not vary):
        refuse(where, f"vary={vary!r}", "is a list of ops, one per repeat (cycling)", ['["same", "steps:1", "same", "end:-1"]'])
    c = _Ctx(key=key, pcs=scale(key, where), where=where, span=line_span(ln, beats_per_bar, every))
    out = []
    for k in range(repeat):
        out += [{**n, "at": n["at"] + k * c.span} for n in _apply(ln, vary[k % len(vary)] if vary else "same", c)]
    return out
