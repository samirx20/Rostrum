"""Where a track or bus plays to, as a pick list in the inspector (no Qt): "Master" and the buses it may feed, storing
the id. The field is a pick in the document's field definitions; the kit puts a "None" first, which an output does not
have (it always plays somewhere), so it is dropped here."""
from __future__ import annotations

from . import strips

FIELD = "output"


def choices(doc, item: dict, label) -> list[dict]:
    """[{value, label}]: the same choices as the Mix page's strip (never itself or a loop)."""
    if item.get("type") == "send":                  # the group a send feeds: every group, by its name
        return [{"value": b["id"], "label": label(b)} for b in doc.data.get("buses", [])]
    if item.get("type") not in ("track", "bus") or nowhere_else(doc.data, item):
        return []
    return [{"value": c["id"], "label": c["label"]}
            for c in strips.routing(item, doc.data.get("buses", []), label)["outputs"]]


def nowhere_else(doc_data: dict, item: dict) -> bool:
    """A track or bus that can only play to the Master (no group to send it to, and it is there now): its Output
    has nothing to pick, so the row is absent (rule of individuality: only what can be used now)."""
    return item.get("type") in ("track", "bus") and item.get(FIELD, "master") in ("", "master") and         not any(b["id"] != item["id"] for b in doc_data.get("buses", []))


def without_none(rows: list[dict]) -> list[dict]:
    return [{**r, "options": [o for o in r["options"] if o["value"] != ""]} if r.get("id") in (FIELD, "bus") and r.get("control") == "" and r.get("type") == "choice" else r
            for r in rows]
