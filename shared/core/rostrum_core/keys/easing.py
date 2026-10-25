"""Easing: how a value travels from one key to the next. A key's `ease` shapes the stretch that starts at it.

Named curves are cubic-beziers (as in CSS); `custom` takes the four points; `spring` and `bounce` overshoot
or rebound; `hold` jumps at the next key; `linear` is straight. The Rust engine implements the same table
(ENGINE_CONTRACT.md › Easing): this file is its reference.
"""
from __future__ import annotations

import math

from .spring import physics_of

BEZIERS = {
    "smooth": (0.25, 0.1, 0.25, 1.0),
    "snappy": (0.16, 1.0, 0.3, 1.0),
    "natural": (0.4, 0.0, 0.2, 1.0),
    "heavy": (0.25, 1.0, 0.5, 1.0),
    "easeIn": (0.42, 0.0, 1.0, 1.0),
    "easeOut": (0.0, 0.0, 0.58, 1.0),
    "easeInOut": (0.65, 0.0, 0.35, 1.0),
}
# THE ONE LIST of eases a person or an agent picks (2D SPEC pro-workflows, base E): `id` is the key's `ease` in the
# document (what key.set {ease} and anim.ease {preset} take, and what inspect gives back), `label` the one word every
# screen says, `job` the shared key map job that sets it (its key: F9 …), `group` "main" (shown first) or "more" (the
# picker's More fold), `curve` 17 points [x, y] for the small picture (added below, from `ease`). "custom" is no row:
# it is what a key becomes when its curve handles are dragged (CUSTOM).
EASE_LIST = [{"id": i, "label": label, "job": job, "group": group} for i, label, job, group in (
    ("linear", "Linear", "", "main"), ("smooth", "Smooth", "smooth", "main"), ("easeIn", "Ease in", "ease_in", "main"),
    ("easeOut", "Ease out", "ease_out", "main"), ("spring", "Spring", "", "main"), ("hold", "Hold", "jump", "main"),
    ("snappy", "Snappy", "", "more"), ("natural", "Natural", "", "more"), ("heavy", "Heavy", "", "more"),
    ("easeInOut", "Stronger smooth", "", "more"), ("bounce", "Bounce", "", "more"))]
CUSTOM = {"id": "custom", "label": "Custom"}
OLD_NAMES = {"in": "easeIn", "out": "easeOut"}      # anim.ease's first preset words, kept for scripts already written
NAMES = [*(e["id"] for e in EASE_LIST), "custom"]
LABELS = {e["id"]: e["label"] for e in (*EASE_LIST, CUSTOM)}


def label_of(name: str) -> str:
    """The one word for an ease ("easeIn" is "Ease in"); an old name reads as its ease's."""
    return LABELS.get(OLD_NAMES.get(name, name), name)


def _bez(p1: float, p2: float, u: float) -> float:
    v = 1 - u
    return 3 * v * v * u * p1 + 3 * v * u * u * p2 + u * u * u


def bezier(x1, y1, x2, y2, x: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(50):            # x is monotone in u for x1, x2 in 0..1
        mid = (lo + hi) / 2
        if _bez(x1, x2, mid) < x:
            lo = mid
        else:
            hi = mid
    return _bez(y1, y2, (lo + hi) / 2)


def spring(x: float, stiffness: float, damping: float) -> float:
    """A damped spring released at 0, settling on 1 (mass 1, the stretch's 0..1 read as one second)."""
    w0 = math.sqrt(stiffness)
    zeta = damping / (2 * w0)
    if zeta < 1:
        wd = w0 * math.sqrt(1 - zeta * zeta)
        return 1 - math.exp(-zeta * w0 * x) * (math.cos(wd * x) + zeta * w0 / wd * math.sin(wd * x))
    return 1 - math.exp(-w0 * x) * (1 + w0 * x)


def bounce(x: float) -> float:
    n, d = 7.5625, 2.75
    if x < 1 / d:
        return n * x * x
    if x < 2 / d:
        x -= 1.5 / d
        return n * x * x + 0.75
    if x < 2.5 / d:
        x -= 2.25 / d
        return n * x * x + 0.9375
    x -= 2.625 / d
    return n * x * x + 0.984375


def ease(key: dict, x: float) -> float:
    """Progress (0 at this key, 1 at the next) for a key's ease at time fraction x in 0..1."""
    name = key.get("ease", "smooth")
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if name == "linear":
        return x
    if name == "hold":
        return 0.0
    if name in BEZIERS:
        return bezier(*BEZIERS[name], x)
    if name == "custom":
        return bezier(key.get("x1", 0.25), key.get("y1", 0.1), key.get("x2", 0.25), key.get("y2", 1.0), x)
    if name == "spring":
        return spring(x, *physics_of(key))       # bounce / speed or stiffness / damping (spring.py)
    if name == "bounce":
        return bounce(x)
    raise ValueError(f'unknown ease "{name}"; accepted: {", ".join(NAMES)}')


for _e in EASE_LIST:
    _e["curve"] = [[round(i / 16, 4), round(ease({"ease": _e["id"]}, i / 16), 4)] for i in range(17)]
