"""Where a track or bus plays to, as a pick list in the inspector (no Qt): "Master" and the buses it may feed, storing
the id. The field is a pick in the document's field definitions; the kit puts a "None" first, which an output does not
have (it always plays somewhere), so it is dropped here."""
from __future__ import annotations

from . import strips

FIELD = "output"


def choices(doc, item: dict, label) -> list[dict]:
    """[{value, label}]: the same choices as the Mix page's strip (never itself or a loop)."""
    if item.get("type") not in ("track", "bus"):
        return []
    return [{"value": c["id"], "label": c["label"]}
            for c in strips.routing(item, doc.data.get("buses", []), label)["outputs"]]


def without_none(rows: list[dict]) -> list[dict]:
    return [{**r, "options": [o for o in r["options"] if o["value"] != ""]} if r.get("id") == FIELD and r.get("control") == "" and r.get("type") == "choice" else r
            for r in rows]
