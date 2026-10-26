"""3D's side of the one animation model on screen (the shared rules: rostrum_gui.route), over 3D's fields table:
what keys may drive and what the inspector shows (values at the playhead). No Qt.
"""
from __future__ import annotations

from rostrum3d import fields as F
from rostrum_core.keys import keys_of
from rostrum_gui.route import KeyRoute


def drives(item: dict, prop: str) -> bool:
    """Keys may drive this field of this item."""
    return prop in F.animatable(item["type"])


def value_at(item: dict, prop: str, t: float):
    keys = keys_of(item, prop)
    if not keys:
        return item.get(prop, F.param(item["type"], prop).default)
    return F.key_value_at(item["type"], prop, keys, t)             # a keyed Visible: on / off, held (never 0.5)


def shown_values(item: dict, t: float) -> dict:
    if item["type"] not in F.KEYED:
        return item
    return {**item, **{p: value_at(item, p, t) for p in {k["prop"] for k in item.get("keys", [])}}}


_route = KeyRoute(F, drives, value_at)
value_call, anim_state, animate_calls = _route.value_call, _route.anim_state, _route.animate_calls


def edit_call(doc, item_id: str, prop: str, value, t: float) -> dict:
    """The call for one field edit. Choosing "Editable mesh" for a shape is the conversion `mesh.edit` (the shape's own
    points become the mesh), never a bare `shape: "poly"` with no points: one source for how a shape turns editable."""
    if prop == "shape" and value == "poly" and doc.item(item_id).get("shape") != "poly":
        return {"op": "mesh.edit", "target": [item_id], "args": {}}
    return _route.edit_call(doc, item_id, prop, value, t)
