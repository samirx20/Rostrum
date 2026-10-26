"""One anchor rule for every text, whoever made it (a person's Text tool, a script, an agent's operation): a one-line
or auto-width text's across anchor follows its paragraph alignment, as After Effects' point text does. Left = its x is
the left edge, Center = the middle, Right = the right edge. So changing Align keeps x and the words re-flow around that
point (Paragraph › Align › Center centres a title on its x).

The anchor stays a stored field (people key it and drag its ring), so Align moves it in the same step that sets the
alignment (`follow`, called by text.set and by a script's text). It follows only while it sits at the old alignment's
own point: an anchor a person or a script placed elsewhere, keyed or driven by an expression is theirs and is kept, and
a text that wraps in a box (`boxWidth`) aligns its lines inside the box, which stays where it is.
"""
from __future__ import annotations

from rostrum_core.keys import keys_of

from . import fields as F

POINT = {"left": 0.0, "center": 0.5, "right": 1.0}     # alignment → its anchor X (0-1 across the text's box)


def _default(name: str):
    return F.param("text", name).default


def follow(before: dict, after: dict, given) -> dict:
    """The anchor X to set with an alignment change: {"anchorX": v}, or {} (nothing follows). `before`: the text's
    fields before the change; `after`: with the change; `given`: the field names the change set itself."""
    if "align" not in given or "anchorX" in given:
        return {}
    old, new = before.get("align", _default("align")), after.get("align", _default("align"))
    ax = before.get("anchorX", _default("anchorX"))
    if old == new or after.get("boxWidth", 0) or keys_of(before, "anchorX") \
            or any(e.get("prop") == "anchorX" for e in before.get("exprs", [])):
        return {}
    return {"anchorX": POINT[new]} if isinstance(ax, (int, float)) and abs(ax - POINT[old]) < 1e-6 else {}


def starts(item: dict) -> dict:
    """What counts as unchanged on a text (the settings panel's starts): its alignment's own anchor X."""
    return {} if item.get("boxWidth", 0) else {"anchorX": POINT.get(item.get("align", _default("align")), 0.5)}
