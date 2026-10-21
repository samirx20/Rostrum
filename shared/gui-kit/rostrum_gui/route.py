"""The one animation model on screen, shared by every app's screen: how a screen edit becomes an operation call and
what the key mark does. No Qt. An app builds one `KeyRoute` over its own fields table and keeps its small
differences (`drives`, `value_at`, `shown_values`, whether an expression decides a field) in its own route.py.

- A number or colour field that keys may drive goes through `value.set` with `at` = the playhead: a still field
  changes; an animated one gets (or changes) a key there. Never the still value of an animated field.
- Everything else (text, choices, toggles, a key's own time / value / ease) is the item's `<type>.set`.
- The inspector shows values at the playhead (`shown_values`, the app's own).
- The key mark: no keys -> `key.add` at the playhead with the value shown; keys -> `key.clear` (stop animating,
  keeping the value at the playhead).
"""
from __future__ import annotations

from collections.abc import Callable

from rostrum_core.keys import keys_of

from .edits import field_call


class KeyRoute:
    """`fields`: the app's fields module (`param(kind, prop)`). `drives(item, prop)`: keys may drive this field.
    `value_at(item, prop, t)`: the field's value at t. `expr_drives(item, prop)`: an expression decides it (no key mark)."""

    def __init__(self, fields, drives: Callable, value_at: Callable, expr_drives: Callable | None = None):
        self.F, self.drives, self.value_at = fields, drives, value_at
        self.expr_drives = expr_drives or (lambda item, prop: False)

    def _arg(self, item: dict, prop: str, value) -> dict:
        p = self.F.param(item["type"], prop)
        if p.type == "color":
            return {"c": value}
        return {"v": int(round(value)) if p.integer else round(float(value), 6)}

    def value_call(self, item: dict, prop: str, value, t: float) -> dict:
        return {"op": "value.set", "target": [item["id"]], "args": {"prop": prop, "at": t, **self._arg(item, prop, value)}}

    def edit_call(self, doc, item_id: str, prop: str, value, t: float) -> dict:
        item = doc.item(item_id)
        if self.drives(item, prop):
            return self.value_call(item, prop, value, t)
        return field_call(doc, item_id, prop, value)

    def anim_state(self, item: dict, prop: str, t: float, fps: float) -> str:
        if not self.drives(item, prop) or self.expr_drives(item, prop):
            return ""
        keys = keys_of(item, prop)
        if not keys:
            return "still"
        return "onkey" if any(abs(k["t"] - t) < 0.5 / fps for k in keys) else "keyed"

    def animate_calls(self, item: dict, prop: str, t: float) -> tuple[list[dict], str]:
        """(calls, history label) for the key mark's toggle."""
        label = self.F.param(item["type"], prop).label
        if keys_of(item, prop):
            return [{"op": "key.clear", "target": [item["id"]], "args": {"prop": prop, "at": t}}], f"Stop animating {label}"
        call = self.value_call(item, prop, self.value_at(item, prop, t), t)
        call["op"] = "key.add"
        call["args"]["t"] = call["args"].pop("at")
        return [call], f"Animate {label}"
