"""Painting a painted fill in place (design 2d-painted-fill § 3.3): which painting the pen paints through the selected
element, the words that say so, and the element's other users. Screen state lives in the painter (`on_fill`: per
element, whether B paints its painted fill or its own paint); this module only reads the document. No Qt.

What B paints on by default: an element with a painted fill and no paint of its own paints the fill; with both, the
one last picked in Layer ▾ (its own paint until then).
"""
from __future__ import annotations

from rostrum2d import paintings
from rostrum2d.kind import LISTS
from rostrum2d.names import display_name
from rostrum_core.tree import walk

OWN, FILL = "own", "fill"


def painting_of(doc, item: dict | None) -> dict | None:
    """The painting an element is filled with (None: no painted fill, or one naming no painting)."""
    if not item or item.get("fillType") != "painted" or not item.get("fillPainting"):
        return None
    return next((p for p in paintings.all_of(doc.data) if p["id"] == item["fillPainting"]), None)


def on_fill(item: dict, chosen: dict) -> bool:
    """B paints the element's painted fill (else its own paint): the choice made in Layer ▾, else the fill when it has no
    paint of its own."""
    return chosen.get(item["id"], not item.get("frames"))


def users(doc, painting_id: str) -> list[dict]:
    return paintings.uses(doc.data, painting_id, LISTS)


def others_in(comp: dict, painting_id: str, but: str) -> list[str]:
    """The other layers of this composition filled with the painting, shown (their edges are dotted while painting)."""
    return [i["id"] for i in walk(comp, LISTS) if i.get("fillType") == "painted" and i.get("fillPainting") == painting_id
            and i["id"] != but and not i.get("hidden")]


def used_by(n: int) -> str:
    return f"used by {n} layers" if n > 1 else "used by this layer only"


def heading(doc, painting: dict, element: dict) -> str:
    """The settings panel's line under "Painting": "Paper grain · painted fill of card 2 · used by 3 layers"."""
    return f'{painting.get("name", "Painting")} · painted fill of {display_name(element)} · {used_by(len(users(doc, painting["id"])))}'


def choices(element: dict, painting: dict) -> list[dict]:
    """Layer ▾'s two groups for an element with a painted fill: its own paint, and the painting."""
    return [{"value": OWN, "label": f"{display_name(element)} · own paint"},
            {"value": FILL, "label": f'{painting.get("name", "Painting")} · painted fill'}]
