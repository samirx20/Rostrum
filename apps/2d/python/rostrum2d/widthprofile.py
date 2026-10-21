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
