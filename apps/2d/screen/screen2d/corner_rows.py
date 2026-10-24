"""Each corner on the settings panel: not a row of its own but a small split icon on the Corner radius row (one radius for
all four corners → a radius per corner), and on the first corner's row the way back. The setting (`eachCorner`) and its
operation are unchanged; agents set it as before. No Qt."""
from __future__ import annotations

ONE, EACH = "radius", "radiusTL"


def rows(rows: list[dict], item: dict | None) -> list[dict]:
    if not item or item.get("type") != "shape" or item.get("shape", "rect") != "rect":
        return rows
    each = bool(item.get("eachCorner"))
    host, button = (EACH, {"label": "One radius for all corners", "icon": "rect", "menu": [], "id": "", "set": ["eachCorner", False]}) if each \
        else (ONE, {"label": "A radius for each corner", "icon": "corners", "menu": [], "id": "", "set": ["eachCorner", True]})
    return [{**r, "button": button} if r.get("row") == "param" and r["id"] == host else r for r in rows]
