"""Keyed values for markup films: any attribute or CSS value an agent writes can be keyed.

A value is a number, a colour (#rgb, #rrggbb, #rrggbbaa; mixed in linear light like the engine's keys) or any text
holding numbers ("M 10 20 C 40 0 …", "blur(4px)", "0 8px 24px #0006"): two texts of the same shape blend number by
number (and colour by colour); texts of different shapes hold until the next key. Easing is Rostrum's one ease table
(rostrum_core.keys.easing), so a markup key eases exactly as a document key does.
"""
from __future__ import annotations

import math
import re

from rostrum_core.keys.easing import NAMES, ease as _ease

_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_TOKEN = re.compile(f"({_HEX.pattern}|{_NUM.pattern})")


def _hex_rgba(h: str) -> list[float]:
    h = h[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        h += "ff"
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4, 6)]


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _srgb(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def mix_colour(a: str, b: str, p: float) -> str:
    ca, cb = _hex_rgba(a), _hex_rgba(b)
    rgb = [_srgb(_lin(x) + (_lin(y) - _lin(x)) * p) for x, y in zip(ca[:3], cb[:3])]
    alpha = min(1.0, max(0.0, ca[3] + (cb[3] - ca[3]) * p))
    out = "#" + "".join(f"{round(v * 255):02x}" for v in rgb)
    return out + (f"{round(alpha * 255):02x}" if alpha < 1 else "")


def _fmt(v: float) -> str:
    r = round(v, 3)
    return str(int(r)) if r == int(r) else f"{r:g}"


def mix(a, b, p: float):
    """a → b at progress p (p may leave 0..1: springs overshoot)."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * p
    sa, sb = str(a), str(b)
    if _HEX.fullmatch(sa) and _HEX.fullmatch(sb):
        return mix_colour(sa, sb, p)
    pa, pb = _TOKEN.split(sa), _TOKEN.split(sb)
    if len(pa) != len(pb) or any(x != y for x, y in zip(pa[0::2], pb[0::2])):
        return a if p < 1 else b                     # different shapes: hold, then jump at the next key
    out = []
    for i, (x, y) in enumerate(zip(pa, pb)):
        if i % 2 == 0:
            out.append(x)
        elif x.startswith("#") or y.startswith("#"):
            out.append(mix_colour(x, y, p) if x.startswith("#") and y.startswith("#") else (x if p < 1 else y))
        else:
            out.append(_fmt(float(x) + (float(y) - float(x)) * p))
    return "".join(out)


def _key(t, v) -> dict:
    """(value) | (value, ease) | (value, {ease, stiffness, …}) | {"v": …, "ease": …} at time t."""
    if isinstance(v, dict) and "v" in v:
        return {"t": float(t), **v}
    if isinstance(v, tuple):
        val, how = v[0], (v[1] if len(v) > 1 else "smooth")
        k = {"t": float(t), "v": val}
        k.update({"ease": how} if isinstance(how, str) else how)
        return k
    return {"t": float(t), "v": v}


class Keys:
    """A keyed value: Keys({0: 0, 1.2: (300, "snappy"), 2: 280}) — call it with a time. The ease written with a key
    shapes the stretch that ARRIVES at it (as CSS keyframes and Remotion's interpolate are usually read); `ease=` sets
    the default. Before the first key and after the last the value holds."""

    def __init__(self, keys: dict, ease: str = "smooth"):
        if not keys:
            raise ValueError("Keys needs at least one {time: value}")
        self.keys = sorted((_key(t, v) for t, v in keys.items()), key=lambda k: k["t"])
        for k in self.keys:
            k.setdefault("ease", ease)
            name = k["ease"]
            if name not in NAMES:
                raise ValueError(f'unknown ease "{name}" at {k["t"]} s; accepted: {", ".join(NAMES)}')

    def __call__(self, t: float):
        ks = self.keys
        if t <= ks[0]["t"]:
            return ks[0]["v"]
        for a, b in zip(ks, ks[1:]):
            if t < b["t"]:
                span = b["t"] - a["t"]
                return mix(a["v"], b["v"], _ease(b, (t - a["t"]) / span) if span > 0 else 1.0)
        return ks[-1]["v"]

    @property
    def end(self) -> float:
        return self.keys[-1]["t"]


def keys(k: dict, ease: str = "smooth") -> Keys:
    return Keys(k, ease)


def lerp(t: float, t0: float, t1: float, v0=0.0, v1=1.0, ease: str = "smooth"):
    """v0 → v1 while t goes t0 → t1, eased, held outside (Remotion's interpolate with clamping)."""
    return Keys({t0: v0, t1: (v1, ease)})(t)


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def spring(t: float, start: float, bounce: float = 0.3, speed: float = 1.0) -> float:
    """0 → 1 from `start`, a damped spring (bounce 0 = none, 0.6 = lively), settling in about 1 / speed s."""
    x = max(0.0, (t - start) * speed)
    zeta = max(0.05, 1.0 - bounce)
    w0 = 9.0
    if zeta < 1:
        wd = w0 * math.sqrt(1 - zeta * zeta)
        return 1 - math.exp(-zeta * w0 * x) * (math.cos(wd * x) + zeta * w0 / wd * math.sin(wd * x))
    return 1 - math.exp(-w0 * x) * (1 + w0 * x)


def wave(t: float, period: float = 1.0, amount: float = 1.0, phase: float = 0.0) -> float:
    """A sine: amount · sin(2π (t / period + phase))."""
    return amount * math.sin(2 * math.pi * (t / period + phase))
