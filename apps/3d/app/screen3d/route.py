"""The one animation model on the 3D screen, in one place: how a screen edit becomes an operation call, what the
inspector shows, and what the key mark does. No Qt. The same rules as 2D's screen2d/route.py, over 3D's fields table
(the 2D file reads rostrum2d's fields, so it can't be called as it is; see README › Shared-layer requests).

- A number or colour field that keys may drive goes through `value.set` with `at` = the playhead: a still field
  changes; an animated one gets (or changes) a key there. Never the still value of an animated field.
- Everything else (text, choices, toggles, materials, shots, a key's own time / value / ease) is `<type>.set`.
- The inspector shows values at the playhead.
- The key mark: no keys -> `key.add` at the playhead with the value shown; keys -> `key.clear` (stop animating,
  keeping the value at the playhead).
"""
from __future__ import annotations

from rostrum2d.evaluate import keys_of, track_value
from rostrum3d import fields as F
from rostrum_gui.edits import field_call


def drives(item: dict, prop: str) -> bool:
    """Keys may drive this field of this item."""
    return prop in F.animatable(item["type"])


def value_at(item: dict, prop: str, t: float):
    keys = keys_of(item, prop)
    return track_value(keys, t) if keys else item.get(prop, F.param(item["type"], prop).default)


def _arg(item: dict, prop: str, value) -> dict:
    p = F.param(item["type"], prop)
    if p.type == "color":
        return {"c": value}
    return {"v": int(round(value)) if p.integer else round(float(value), 6)}


def value_call(item: dict, prop: str, value, t: float) -> dict:
    return {"op": "value.set", "target": [item["id"]], "args": {"prop": prop, "at": t, **_arg(item, prop, value)}}


def edit_call(doc, item_id: str, prop: str, value, t: float) -> dict:
    item = doc.item(item_id)
    if drives(item, prop):
        return value_call(item, prop, value, t)
    return field_call(doc, item_id, prop, value)


def shown_values(item: dict, t: float) -> dict:
    if item["type"] not in F.ITEMS:
        return item
    return {**item, **{p: value_at(item, p, t) for p in {k["prop"] for k in item.get("keys", [])}}}


def anim_state(item: dict, prop: str, t: float, fps: float) -> str:
    if not drives(item, prop):
        return ""
    keys = keys_of(item, prop)
    if not keys:
        return "still"
    return "onkey" if any(abs(k["t"] - t) < 0.5 / fps for k in keys) else "keyed"


def animate_calls(item: dict, prop: str, t: float) -> tuple[list[dict], str]:
    """(calls, history label) for the key mark's toggle."""
    label = F.param(item["type"], prop).label
    if keys_of(item, prop):
        return [{"op": "key.clear", "target": [item["id"]], "args": {"prop": prop, "at": t}}], f"Stop animating {label}"
    call = value_call(item, prop, value_at(item, prop, t), t)
    call["op"] = "key.add"
    call["args"]["t"] = call["args"].pop("at")
    return [call], f"Animate {label}"
