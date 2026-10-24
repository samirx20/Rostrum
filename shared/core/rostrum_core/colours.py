"""The one reader of a colour as a person or an agent writes it. Stored colours are "#rrggbb"; "#rgb" is the same
colour written short and is widened to it. Anything else is refused with the exact text to write instead: a CSS name
gets its hex in the hint but is never taken silently (CSS's "green" is #008000, not the green most people mean), and
a colour with transparency (#rrggbbaa, rgba(…)) points at the opacity field, where transparency lives."""
from __future__ import annotations

import re

HEX6 = re.compile(r"^#[0-9a-fA-F]{6}$")
HEX3 = re.compile(r"^#[0-9a-fA-F]{3}$")
SCHEMA = r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"       # what MCP clients may send (read() widens the short form)
FORMS = ['"#ff7a59"', '"#fff" (short for "#ffffff")']
NAMES = {"white": "#ffffff", "black": "#000000", "red": "#ff0000", "green": "#008000", "lime": "#00ff00",
         "blue": "#0000ff", "yellow": "#ffff00", "orange": "#ffa500", "purple": "#800080", "gray": "#808080",
         "grey": "#808080", "pink": "#ffc0cb", "cyan": "#00ffff", "magenta": "#ff00ff"}


def read(value) -> str | None:
    """The colour as stored ("#rrggbb", as written), or None when it isn't one."""
    if not isinstance(value, str):
        return None
    if HEX6.match(value):
        return value
    if HEX3.match(value):
        return "#" + "".join(c * 2 for c in value[1:])
    return None


def hint(value) -> str | None:
    """What to write instead of a value read() refused."""
    if not isinstance(value, str):
        return 'A colour is text: write "#ffffff"'
    v = value.strip().lower()
    if v in NAMES:
        return f'Write "{NAMES[v]}" for {v}'
    if v in ("none", "transparent"):
        return "For no colour, set the layer's opacity (or fillOpacity) to 0, or turn the fill off (filled=False)"
    if re.match(r"^#([0-9a-f]{8}|[0-9a-f]{4})$", v) or v.startswith(("rgba", "hsla")):
        return "Transparency is not part of a colour here: write the colour as #rrggbb and set opacity (or fillOpacity)"
    if m := re.match(r"^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$", v):
        return f'Write "#{"".join(f"{min(int(n), 255):02x}" for n in m.groups())}"'
    if re.match(r"^[0-9a-f]{6}$", v):
        return f'Start it with #: "#{v}"'
    return None
