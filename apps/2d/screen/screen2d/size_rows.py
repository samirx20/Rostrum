"""Scene settings › Size: a choice among the named frame sizes (rostrum2d/frame_sizes.py, one list of data), first in the
Frame group; the scene's own Width and Height rows stay under it for any other numbers. Not a stored field: the pick is
the agents' `comp.size`, and the row shows whichever named size the scene's numbers match (else "Custom"). No Qt."""
from __future__ import annotations

from rostrum2d import frame_sizes

ROW = "size"


def rows(rows: list[dict], item: dict | None) -> list[dict]:
    if not item or item.get("type") != "comp":
        return rows
    at = next((n for n, r in enumerate(rows) if r["row"] == "param" and r["id"] == "width"), None)
    if at is None:
        return rows
    w, h = item.get("width", 1920), item.get("height", 1080)
    row = {**rows[at], "id": ROW, "label": "Size", "type": "choice", "options": frame_sizes.options(w, h),
           "value": frame_sizes.named(w, h) or "custom", "min": None, "max": None, "unit": "", "anim": "", "help": "A named frame size; "
           "or type Width and Height below"}
    return rows[:at] + [row] + rows[at:]


def call(item_id: str, value) -> dict:
    return {"op": "comp.size", "target": [item_id], "args": {"size": value}}
