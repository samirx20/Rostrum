"""Camera rigs: a rig's values at one moment → the transform it gives what rides on it. The compiler sends a rig to
the core as a plain group whose transform is baked per frame (ENGINE_CONTRACT.md: the core never sees a rig), so a
rig plays the same in Storm, Cycles and any USD program, and an aim inside a rig still works.

In the rig's own space (its x y z and turns are the base): the head sits at
  orbit  (radius·sin a, height, radius·cos a), facing the centre (a = 0 is on +Z, towards the default camera);
  crane  the arm's tip: length L from the base, lifted `lift`, swung `swing` (0 = forward, the rig's −Z);
  dolly  `travel` metres forward (−Z).
then turns by pan (around up) and tilt; handheld adds smooth, seeded noise (the same every render).
"""
from __future__ import annotations

import math

from . import aim

_PRIMES = (1.0, 1.731, 2.519)        # three octave-ish rates per channel, not multiples, so the drift never loops


def _hash(seed: int, channel: int, k: int) -> float:
    """A repeatable number in -1..1 for lattice point k."""
    n = (k * 374761393 + channel * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0


def _smooth_noise(seed: int, channel: int, x: float) -> float:
    k = math.floor(x)
    f = x - k
    f = f * f * f * (f * (f * 6 - 15) + 10)            # smootherstep: no kinks, so no visible jolts
    return _hash(seed, channel, k) * (1 - f) + _hash(seed, channel, k + 1) * f


def drift(seed: int, channel: int, t: float, hz: float) -> float:
    """Handheld noise in about -1..1: a few layers of smooth value noise, the slowest strongest."""
    total = sum(_smooth_noise(seed, channel * 3 + i, t * hz * r + 17.0 * i) / (i + 1) for i, r in enumerate(_PRIMES))
    return total / 1.5


def _head(v: dict) -> tuple[list[float], float, float]:
    """Head position (rig space) and its facing (yaw, pitch in degrees) before pan, tilt and shake."""
    if v["rig"] == "orbit":
        a, r, h = math.radians(v["angle"]), v["radius"], v["height"]
        return [r * math.sin(a), h, r * math.cos(a)], v["angle"], -math.degrees(math.atan2(h, r)) if r or h else 0.0
    if v["rig"] == "crane":
        s, lift, length = math.radians(v["swing"]), math.radians(v["lift"]), v["armLength"]
        reach = length * math.cos(lift)
        return [-reach * math.sin(s), length * math.sin(lift), -reach * math.cos(s)], v["swing"], 0.0
    return [0.0, 0.0, -v["travel"]], 0.0, 0.0


def _euler_xyz(m) -> tuple[float, float, float]:
    """rx ry rz (degrees) with m = Rz·Ry·Rx, the order aim.local uses."""
    ry = math.asin(max(-1.0, min(1.0, -m[2][0])))
    if abs(math.cos(ry)) > 1e-9:
        rx, rz = math.atan2(m[2][1], m[2][2]), math.atan2(m[1][0], m[0][0])
    else:                                                  # straight up or down: put all the turn in rx
        rx, rz = math.atan2(-m[1][2], m[1][1]), 0.0
    return math.degrees(rx), math.degrees(ry), math.degrees(rz)


def transform(v: dict, t: float) -> dict:
    """The rig's x y z rx ry rz (sx sy sz = 1) in its parent's space at time t (seconds), from its values then."""
    pos, yaw, pitch = _head(v)
    yaw, pitch, roll = yaw + v["pan"], pitch + v["tilt"], 0.0
    if v["handheld"]:
        seed, hz, amp, sway = int(v["seed"]), v["shakeFrequency"], v["shake"], v["shakeMove"]
        yaw += amp * drift(seed, 0, t, hz)
        pitch += amp * drift(seed, 1, t, hz)
        roll += 0.5 * amp * drift(seed, 2, t, hz)
        pos = [p + sway * drift(seed, 3 + i, t, hz * 0.7) for i, p in enumerate(pos)]
    one = {"sx": 1.0, "sy": 1.0, "sz": 1.0}
    head = aim.local({"x": 0, "y": 0, "z": 0, "rx": pitch, "ry": yaw, "rz": 0.0, **one})
    head = (aim._mul(head[0], aim._rot(2, roll)), pos)    # roll about the view axis, applied first
    base = aim.local({**{k: v[k] for k in ("x", "y", "z", "rx", "ry", "rz")}, **one})
    m, p = aim.compose(base, head)
    rx, ry, rz = _euler_xyz(m)
    return {"x": p[0], "y": p[1], "z": p[2], "rx": rx, "ry": ry, "rz": rz, **one}


def _near(a: float, ref: float) -> float:
    return a + 360.0 * round((ref - a) / 360.0)


def continuous(turns: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """rx ry rz per frame, made continuous: each frame takes whichever of its two equal Euler forms (rx, ry, rz) or
    (rx+180, 180-ry, rz+180) lies nearest the frame before, unwrapped by whole turns, so no in-between sample
    (motion blur, a USD program's interpolation) spins the long way round."""
    out = []
    for rx, ry, rz in turns:
        forms = [(rx, ry, rz), (rx + 180.0, 180.0 - ry, rz + 180.0)]
        if out:
            prev = out[-1]
            forms = [tuple(_near(a, b) for a, b in zip(f, prev)) for f in forms]
            out.append(min(forms, key=lambda f: sum(abs(a - b) for a, b in zip(f, prev))))
        else:
            out.append(forms[0])
    return out
