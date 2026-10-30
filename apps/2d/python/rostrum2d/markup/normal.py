"""Markup a browser reads one way, written the way this engine reads it the same (meaning unchanged, nothing refused).

- `color="…"` on an SVG element is a presentation attribute (it sets what `currentColor` means below it); the engine's
  style system reads `color` only from CSS, so it moves into the element's style (the element's own style wins)."""
from __future__ import annotations

import re

from .apply import SVG_TAGS

_COLOR = re.compile(r"(<([A-Za-z][\w:-]*)\b[^<>]*?)\scolor\s*=\s*([\"'])([^\"'<>]*)\3([^<>]*>)")
_STYLE = re.compile(r"\sstyle\s*=\s*([\"'])(.*?)\1", re.S)


def _one(m: re.Match) -> str:
    if m.group(2) not in SVG_TAGS:
        return m.group(0)
    whole, value = m.group(1) + m.group(5), m.group(4).strip()
    style = _STYLE.search(whole)
    if style is None:
        return f'{m.group(1)} style="color: {value}"{m.group(5)}'
    if re.search(r"(?:^|;)\s*color\s*:", style.group(2)):
        return whole                                        # the element's own style wins, as in a browser
    q = style.group(1)
    return whole.replace(style.group(0), f" style={q}color: {value}; {style.group(2)}{q}", 1)


def svg_color(markup: str) -> str:
    if "color=" not in markup:
        return markup
    return _COLOR.sub(_one, markup)
