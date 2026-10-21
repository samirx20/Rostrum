"""Motion events read from sampled picture motion (data from the 2D app, read-only): per layer its position, scale
and opacity at `rate` samples a second. Out come the events a sound can follow, with their exact times:

  move   a stretch where the layer travels: start, peak speed and when, stop, the speed curve over it, from / to,
         whether it starts / ends on screen, and `lands` (when it arrives on screen: the time it first reaches its
         resting place, how hard: its speed then against its peak)
  press  the scale dips and comes back (a button tapped): the time of the deepest point and of the release
  snap   the scale jumps to its resting value (a title snapping in): its most sudden moment
  step   the opacity jumps on (a counter's digit, a cut-in): the time

Facts only; what they sound like is `score.py`'s starting point, every value editable after.
"""
from __future__ import annotations

import math

MOVING_PX_S = 40.0        # slower than this is standing still
SCALING_PER_S = 0.25      # a scale changing slower than this is still
SPEED_POINTS = 24         # points in a move's speed curve


def _segments(v: list[float], floor: float) -> list[tuple[int, int]]:
    out, start = [], None
    for i, x in enumerate(v + [0.0]):
        if x > floor and start is None:
            start = i
        elif x <= floor and start is not None:
            out.append((start, i))
            start = None
    return out


def _on_screen(x, y, w, h, s):
    return -0.02 * w <= x <= 1.02 * w and -0.02 * h <= y <= 1.02 * h


def _curve(v: list[float], i0: int, i1: int, peak: float) -> list[list[float]]:
    n = i1 - i0
    pts = [[0.0, round(v[i0] / peak, 3)]]
    for k in range(1, SPEED_POINTS):
        i = i0 + round(k * n / SPEED_POINTS)
        pts.append([round(k / SPEED_POINTS, 4), round(min(v[i] / peak, 1.0), 3)])
    pts.append([1.0, 0.0])
    return pts


def _moves(lid: str, L: dict, rate: float, W: float, H: float) -> list[dict]:
    xs, ys = L["x"], L["y"]
    v = [math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) * rate for i in range(len(xs) - 1)]
    out = []
    for i0, i1 in _segments(v, MOVING_PX_S):
        ip = max(range(i0, i1), key=v.__getitem__)
        peak = v[ip]
        a, b = (xs[i0], ys[i0]), (xs[i1], ys[i1])
        ev = {"layer": lid, "kind": "move", "at": i0 / rate, "end": i1 / rate, "peak_at": (ip + 0.5) / rate,
              "peak_speed": round(peak, 1), "from": list(a), "to": list(b), "distance": round(math.dist(a, b), 1),
              "speed": _curve(v, i0, i1, peak), "x": [xs[i0 + round(k * (i1 - i0) / 8)] for k in range(9)],
              "area": (L.get("w") or 0) * (L.get("h") or 0),
              "on_screen": [_on_screen(*a, W, H, 1), _on_screen(*b, W, H, 1)], "lands": None}
        if ev["on_screen"][1]:
            ev["lands"] = _landing(xs, ys, v, ip, i1, b, a, rate)
        out.append(ev)
    return out


def _landing(xs, ys, v, ip, i1, rest, origin, rate) -> dict:
    """When the layer first reaches its resting place (an overshoot crosses it; an ease-out just arrives)."""
    dx, dy = rest[0] - origin[0], rest[1] - origin[1]
    norm = math.hypot(dx, dy) or 1.0
    ahead = [((rest[0] - xs[i]) * dx + (rest[1] - ys[i]) * dy) / norm for i in range(ip, i1 + 1)]
    k = next((j for j, d in enumerate(ahead) if d <= 0.5), len(ahead) - 1)
    i = ip + k
    return {"at": i / rate, "hardness": round(min(1.0, v[min(i, len(v) - 1)] / max(v[ip], 1e-9)), 3),
            "overshoots": any(d < -2.0 for d in ahead)}


def _scales(lid: str, s: list[float], rate: float) -> list[dict]:
    ds = [abs(s[i + 1] - s[i]) * rate for i in range(len(s) - 1)]
    segs = []
    for seg in _segments(ds, SCALING_PER_S):      # a dip's way down and back up are one gesture
        if segs and seg[0] - segs[-1][1] <= 2:
            segs[-1] = (segs[-1][0], seg[1])
        else:
            segs.append(seg)
    out = []
    for i0, i1 in segs:
        lo = min(range(i0, i1 + 1), key=s.__getitem__)
        if s[lo] < min(s[i0], s[i1]) - 0.02:
            out.append({"layer": lid, "kind": "press", "at": lo / rate, "release": i1 / rate,
                        "depth": round(min(s[i0], s[i1]) - s[lo], 3)})
        elif abs(s[i0] - s[i1]) > 0.05:
            # The snap is heard at its most sudden moment: where the scale changes fastest.
            k = max(range(i0, i1), key=ds.__getitem__)
            out.append({"layer": lid, "kind": "snap", "at": k / rate, "start": i0 / rate, "end": i1 / rate,
                        "from": s[i0], "to": s[i1]})
    return out


def _steps(lid: str, o: list[float], rate: float) -> list[dict]:
    return [{"layer": lid, "kind": "step", "at": (i + 1) / rate} for i in range(len(o) - 1) if o[i + 1] - o[i] > 0.5]


def events(samples: dict) -> list[dict]:
    """Every event of every layer, in time order."""
    rate, W, H = samples["rate"], samples["width"], samples["height"]
    out = []
    for lid, L in samples["layers"].items():
        out += _moves(lid, L, rate, W, H) + _scales(lid, L["scale"], rate) + _steps(lid, L["opacity"], rate)
    for e in out:
        for k in ("at", "end", "peak_at", "release", "start"):
            if k in e:
                e[k] = round(e[k], 4)
    return sorted(out, key=lambda e: e["at"])
