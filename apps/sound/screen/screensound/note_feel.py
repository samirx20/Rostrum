"""A note's own playing fields in words (no Qt): Swell (its `dynamics` curve), Vibrato and Bend, as the inspector shows
them and as a person types them. The document keeps its data forms ([[x, y], …], {rate, depth, delay}); here they
read and are typed as plain numbers with units:

    Swell    "0.8" (the whole note at 0.8 of its level), "0.5 → 1.5" (a swell from start to end), "0.5 → 1.2 → 0.8"
             (points spread evenly); 1 = as played. A point not on the even spread says where: "1.2 at 30%".
    Vibrato  "30 cents · 5.5 Hz · after 0.2 s"; typed "30" is 30 cents at 5.5 Hz; "off" (or 0) has none.
    Bend     "-100 cents" (the whole note), "0 → 200 cents" (a slide across the note); "0" has none.

`words` and `parse` are each other's way back, so a field typed in shows as typed.
"""
from __future__ import annotations

import re

PARAMS = ("dynamics", "vibrato", "bend")
LABELS = {"dynamics": "Swell", "vibrato": "Vibrato", "bend": "Bend"}
HELP = {"dynamics": "The note's level across its length (1 = as played): one number for all of it (0.8), start → end "
                    "for a swell or a fade (0.5 → 1.5), or several spread evenly (0.5 → 1.2 → 0.8). 0 … 2.",
        "vibrato": "Depth in cents, then speed in Hz, then how long it waits: 30 · 5.5 Hz · after 0.2 s. "
                   "One number is the depth (at 5.5 Hz). Off or 0: none.",
        "bend": "Pitch bend in cents (100 = a half step): one number bends the whole note (-100), start → end "
                "slides across it (0 → 200). 0: none."}
EXAMPLE = {"dynamics": "type a level like 0.8, or 0.5 → 1.5 for a swell", "bend": "type cents like -100, or 0 → 200 for a slide"}
RATE = 5.5
NUM = r"-?\d+(?:\.\d+)?"
_POINT = re.compile(rf"^({NUM})(?:\s*(?:cents?|c))?(?:\s+at\s+({NUM})\s*(%|s)?)?$")


def _n(v: float) -> str:
    return f"{float(v):.3f}".rstrip("0").rstrip(".") or "0"


def words(param: str, value, secs: float) -> str:
    """How the field reads (`secs`: the note's length in seconds, where a bend's points sit)."""
    if param == "vibrato":
        if not value or not float(value.get("depth", 0)):
            return "off"
        out = f"{_n(value['depth'])} cents · {_n(value.get('rate', RATE))} Hz"
        return out + (f" · after {_n(value['delay'])} s" if value.get("delay") else "")
    unit = " cents" if param == "bend" else ""
    if not value:
        return ("0" if param == "bend" else "1") + unit
    span = 1.0 if param == "dynamics" else max(secs, 1e-6)
    n, out = len(value), []
    for i, (x, y) in enumerate(value):
        even = (i / (n - 1) if n > 1 else 0.0) * span
        where = "" if abs(x - even) <= 0.01 * span else (f" at {_n(100 * x)}%" if param == "dynamics" else f" at {_n(x)} s")
        out.append(_n(y) + where)
    return " → ".join(out) + unit


def _range(param, v, lo, hi, what):
    if not lo <= v <= hi:
        raise ValueError(f"{what} {_n(v)} is outside {_n(lo)} … {_n(hi)}")
    return v


def parse(param: str, text: str, secs: float):
    """The typed words as the document's value (None: none, the note plays plainly). Raises ValueError in plain words."""
    t = str(text).strip().lower().replace("−", "-")
    if t in ("", "off", "none", "no"):
        return None
    if param == "vibrato":
        found = {}
        for num, unit in re.findall(rf"({NUM})\s*(cents?|c|hz|s)?\b", t):
            key = {"hz": "rate", "s": "delay"}.get(unit, "depth" if unit else
                                                  next(k for k in ("depth", "rate", "delay", "x") if k not in found))
            found[key] = float(num)
        if not found or "x" in found:
            raise ValueError("type the depth in cents, then the speed in Hz, then the wait in s: 30 · 5.5 Hz · after 0.2 s")
        if not found.get("depth"):
            return None
        out = {"rate": _range(param, found.get("rate", RATE), 0.1, 20, "speed"),
               "depth": _range(param, found["depth"], 0, 200, "depth")}
        if found.get("delay"):
            out["delay"] = _range(param, found["delay"], 0, 30, "wait")
        return out
    parts = [p.strip() for p in re.split(r"→|->|,|;", t.replace("cents", "").replace("cent", "")) if p.strip()]
    if len(parts) == 1 and len(parts[0].split()) > 1 and " at " not in f" {parts[0]} ":
        parts = parts[0].split()                       # "0.5 1.5": points spread evenly, as with arrows
    pts = []
    for i, p in enumerate(parts):
        m = _POINT.match(p)
        if not m:
            raise ValueError(f'"{p}" is not a number: {EXAMPLE[param]}')
        y = float(m.group(1))
        span = 1.0 if param == "dynamics" else max(secs, 1e-6)
        x = (i / (len(parts) - 1) if len(parts) > 1 else 0.0) * span
        if m.group(2) is not None:
            x = float(m.group(2)) / 100 if m.group(3) == "%" or (param == "dynamics" and m.group(3) != "s") else float(m.group(2))
        pts.append([round(x, 4), _range(param, y, *((0, 2) if param == "dynamics" else (-2400, 2400)),
                                        "a level" if param == "dynamics" else "a bend")])
    pts.sort(key=lambda q: q[0])
    flat = len(pts) == 1 or all(abs(q[1] - pts[0][1]) < 1e-9 for q in pts)
    if flat and pts[0][1] == (1.0 if param == "dynamics" else 0.0):
        return None                                    # as played
    if param == "dynamics" and len(pts) == 1:
        return [[0.0, pts[0][1]], [1.0, pts[0][1]]]
    return pts
