"""Shutter (motion blur) and the trail / smear effects (MOTION.md). STUB by the lead; member B owns it."""
from __future__ import annotations

from ..fields import N, S  # noqa: F401  (the table helpers)

COMP = [
    N("shutter", "Shutter angle", "Motion blur", 0, 720, 1, "°", S, default=0.0),
    N("shutterSamples", "Blur samples", "Motion blur", 2, 64, 1, "", S, integer=True, default=8),
]
FIELDS = {
    "trail": [
        N("copies", "Copies", "Trail", 1, 32, 1, "", integer=True, default=4),
        N("spacing", "Spacing", "Trail", 0.25, 30, 0.25, "f", default=2.0),
        N("fade", "Fade", "Trail", 0, 1, 0.01, "", default=0.6),
    ],
    "smear": [
        N("amount", "Amount", "Smear", 0, 10, 0.01, "", default=1.0),
        N("max", "Longest", "Smear", 1, 20, 0.1, "×", default=4.0),
    ],
}
EFFECTS = ("trail", "smear")
LABELS = {"trail": "Trail", "smear": "Smear"}
STILL: dict = {}
