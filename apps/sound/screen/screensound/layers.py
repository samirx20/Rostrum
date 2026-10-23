"""Layered sounds as the settings panel shows them (no Qt): the clips of one track with the same `group` name are
one sound made of several layers (rostrum_sound/doc/ops_group.py's `mates`: the same rule). Absent (nothing
returned) unless one clip is selected, it has a group, and that group has another member."""
from __future__ import annotations

from . import timing


def of(doc, ids: list[str]) -> dict:
    """{"group": name, "rows": [{id, label, what, here}]} in time order, or {} when there is nothing to show."""
    if len(ids) != 1 or not doc.has(ids[0]):
        return {}
    item = doc.item(ids[0])
    if item["type"] != "clip" or not item.get("group"):
        return {}
    track = doc.item(doc.parent_of(ids[0])[0])
    others = [c for c in track.get("clips", [])
              if c.get("group") == item["group"] and c["id"] != item["id"]]
    if not others:
        return {}
    layers = sorted([item, *others], key=lambda it: (timing.sec(it["at"], doc.data, it["id"]), it["id"]))
    return {"group": item["group"], "rows": [
        {"id": it["id"], "label": f"Layer {n}", "what": f'at {timing.sec(it["at"], doc.data, it["id"]):g} s',
         "here": it["id"] == ids[0]} for n, it in enumerate(layers, 1)]}

