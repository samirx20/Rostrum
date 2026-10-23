"""The colour a NEW text starts in: light or dark, by contrast with what is under it where it is created (one place).

White text on a light grey new shape was hard to read, so a new text asks the frame the canvas shows (what the person
sees: a shape, a picture, a gradient, or the empty background) and takes dark ink on a light spot, white on a dark one.
A colour the person already picked while typing (the start look) always wins; this only fills the gap. Not a style
rule: it is what keeps a text visible, like the brush's starting colour (brush.starting_colour). No Qt.
"""
from __future__ import annotations

DARK, LIGHT = "#1a1a1a", "#ffffff"


def luminance(colour: str) -> float | None:
    h = (colour or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ink_for(under: str, background: str = "") -> str:
    """Dark ink on a light spot, white on a dark one; `under` = the frame's colour there ("" = clear: use `background`)."""
    lum = luminance(under)
    if lum is None:
        lum = luminance(background)
    return LIGHT if lum is None or lum < 0.5 else DARK
