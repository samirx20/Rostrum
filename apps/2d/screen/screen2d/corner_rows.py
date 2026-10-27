"""Each corner on the settings panel: not a row of its own but a small split icon on the Corner radius row (one radius for
all four corners → a radius per corner), and on the first corner's row the way back. The setting (`eachCorner`) and its
operation are unchanged; agents set it as before. No Qt."""
from __future__ import annotations

ONE, EACH = "radius", "radiusTL"
# each corner: where it is across and down the box (0 / 1) and its field's ending; the canvas's radius dots use the same
# (shape_handle_geom.py: an Alt-drag on one dot switches Each corner on and sets only that corner's radius)
CORNERS = {"nw": (0, 0, "TL"), "ne": (1, 0, "TR"), "se": (1, 1, "BR"), "sw": (0, 1, "BL")}


def rows(rows: list[dict], item: dict | None) -> list[dict]:
    if not item or item.get("type") != "shape" or item.get("shape", "rect") != "rect":
        return rows
    each = bool(item.get("eachCorner"))
    host, button = (EACH, {"label": "One radius for all corners", "icon": "rect", "menu": [], "id": "", "set": ["eachCorner", False]}) if each \
        else (ONE, {"label": "A radius for each corner", "icon": "corners", "menu": [], "id": "", "set": ["eachCorner", True]})
    return [{**r, "button": button} if r.get("row") == "param" and r["id"] == host else r for r in rows]
