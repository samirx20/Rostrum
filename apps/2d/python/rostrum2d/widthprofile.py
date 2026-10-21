"""A path stroke's width profile: the text "pos,mult pos,mult …" (pos 0..1 along the line, mult ≥ 0 times strokeWidth;
empty = an even width). The one parser: the operation, the scene check and the widest-point lookup all use it
(the engine reads the same text: scene/ stroke width)."""
from __future__ import annotations


def parse(text: str) -> list[tuple[float, float]]:
    """The (pos, mult) pairs of a profile text; ValueError says what is wrong. Empty text = no profile."""
    out: list[tuple[float, float]] = []
    for word in text.split():
        try:
            pos, mult = (float(v) for v in word.split(","))
        except ValueError:
            raise ValueError(f'"{word}" is not "pos,mult" (two numbers, like 0.5,1.5)') from None
        if not 0 <= pos <= 1:
            raise ValueError(f"position {pos:g} is outside 0 to 1 (0 = the start of the line, 1 = its end)")
        if not mult >= 0:
            raise ValueError(f"width multiplier {mult:g} at {pos:g} is negative (0 or more)")
        if out and pos <= out[-1][0]:
            raise ValueError(f"position {pos:g} is not after the one before it ({out[-1][0]:g}); positions must increase")
        out.append((pos, mult))
    return out


def format(pairs) -> str:
    return " ".join(f"{p:.6g},{m:.6g}" for p, m in pairs)


def widest(item: dict) -> float:
    """The widest the item's stroke gets, in px: strokeWidth × the biggest profile multiplier (tapers only narrow)."""
    base = item.get("strokeWidth", 0.0)
    try:
        mults = [m for _, m in parse(item.get("widthProfile", ""))]
    except ValueError:
        mults = []
    return base * max(mults, default=1.0)


def at(pairs, u: float) -> float:
    """The multiplier at u, as the engine draws it (scene/width_profile.rs `at`): 1 with no points, held outside them,
    a monotone cubic (Fritsch–Butland tangents) between them, never below 0."""
    n = len(pairs)
    if n == 0:
        return 1.0
    if n == 1 or u <= pairs[0][0]:
        return pairs[0][1]
    if u >= pairs[-1][0]:
        return pairs[-1][1]
    slope = [(pairs[k + 1][1] - pairs[k][1]) / (pairs[k + 1][0] - pairs[k][0]) for k in range(n - 1)]

    def tangent(k):
        if k == 0 or k == n - 1:
            return slope[min(k, n - 2)]
        a, b = slope[k - 1], slope[k]
        return 0.0 if a * b <= 0 else 2 * a * b / (a + b)
    i = next(k for k in range(n - 1) if u < pairs[k + 1][0])
    (x0, y0), (x1, y1) = pairs[i], pairs[i + 1]
    h = x1 - x0
    t = (u - x0) / h
    t2, t3 = t * t, t * t * t
    y = ((2 * t3 - 3 * t2 + 1) * y0 + (t3 - 2 * t2 + t) * h * tangent(i) + (3 * t2 - 2 * t3) * y1
         + (t3 - t2) * h * tangent(i + 1))
    return max(y, 0.0)


def blend(a, b, p: float) -> list[tuple[float, float]]:
    """Two profiles at eased progress p (one key to the next), as the engine (width_profile.rs `blend`): at every
    position of either, both multipliers (`at`, an empty profile is 1) mixed by p, never below 0."""
    return [(u, max(at(a, u) + (at(b, u) - at(a, u)) * p, 0.0)) for u in sorted({u for u, _ in [*a, *b]})]


def track(keys: list[dict], t: float) -> str:
    """A widthProfile track's text at time t (its keys keep their text in `d`), blended between keys."""
    from rostrum_core.keys import ease
    if t <= keys[0]["t"]:
        return keys[0]["d"]
    for k0, k1 in zip(keys, keys[1:]):
        if t < k1["t"]:
            p = ease(k0, (t - k0["t"]) / (k1["t"] - k0["t"]))
            return format(blend(parse(k0["d"]), parse(k1["d"]), p))
    return keys[-1]["d"]
