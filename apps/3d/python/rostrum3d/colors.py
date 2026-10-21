"""Document colours are #rrggbb in sRGB (what people pick); the scene description is linear Rec.709."""
from __future__ import annotations


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear(hex_: str) -> list[float]:
    return [round(_lin(int(hex_[i:i + 2], 16) / 255), 6) for i in (1, 3, 5)]
