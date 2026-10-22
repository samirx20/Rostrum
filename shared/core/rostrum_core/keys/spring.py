"""A spring as a person says it: **bounce** (0 none – 1 a lot) and **speed** (0 slow – 1 fast). The one place these
words become the physics the evaluator and the engines read (`stiffness`, `damping`: mass 1, the stretch's 0..1 read
as one second; easing.spring). A key may carry either pair: bounce / speed win when present (what the key bar and
`key.set {ease: "spring", bounce, speed}` write); stiffness / damping alone are an expert's numbers, read back as
bounce / speed for the key bar. The defaults (bounce 0.6, speed 0.5) are the old stiffness 170, damping 12 (to 0.05 %).

    damping ratio  zeta = 1 - 0.9 * bounce          (0 → no overshoot, 1 → rings a lot)
    natural speed  w0   = sqrt(170) * 3 ** (2 * speed - 1)   (0 → about a third as fast, 1 → three times)
"""
from __future__ import annotations

import math

BOUNCE, SPEED = 0.6, 0.5                 # the defaults, = stiffness 170, damping 12
STIFFNESS, DAMPING = 170.0, 12.0
_W0 = math.sqrt(STIFFNESS)


def physics(bounce: float, speed: float) -> tuple[float, float]:
    """(stiffness, damping) for bounce and speed in 0..1."""
    b, s = min(max(bounce, 0.0), 1.0), min(max(speed, 0.0), 1.0)
    w0 = _W0 * 3 ** (2 * s - 1)
    return w0 * w0, 2 * (1 - 0.9 * b) * w0


def feel(stiffness: float, damping: float) -> tuple[float, float]:
    """(bounce, speed) for a stiffness and damping, clamped to 0..1 (the inverse of `physics`)."""
    w0 = math.sqrt(max(stiffness, 1e-9))
    zeta = damping / (2 * w0)
    bounce = (1 - zeta) / 0.9
    speed = (math.log(w0 / _W0, 3) + 1) / 2
    return round(min(max(bounce, 0.0), 1.0), 4), round(min(max(speed, 0.0), 1.0), 4)


def feel_of(key: dict) -> tuple[float, float]:
    """The bounce and speed a key's spring has, whichever pair it was written with."""
    b, s = feel(key.get("stiffness", STIFFNESS), key.get("damping", DAMPING))
    return key.get("bounce", b), key.get("speed", s)


def physics_of(key: dict) -> tuple[float, float]:
    """(stiffness, damping) of a key's spring: from bounce / speed when it has them, else its own numbers."""
    if "bounce" in key or "speed" in key:
        return physics(*feel_of(key))
    return key.get("stiffness", STIFFNESS), key.get("damping", DAMPING)
