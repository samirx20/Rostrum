"""The one animation model on screen, shared by every app's screen: how a screen edit becomes an operation call and
what the key mark does. No Qt. An app builds one `KeyRoute` over its own fields table and keeps its small
differences (`drives`, `value_at`, `shown_values`, whether an expression decides a field) in its own route.py.

- A number or colour field that keys may drive goes through `value.set` with `at` = the playhead: a still field
  changes; an animated one gets (or changes) a key there. Never the still value of an animated field.
- Everything else (text, choices, toggles, a key's own time / value / ease) is the item's `<type>.set`.
- The inspector shows values at the playhead (`shown_values`, the app's own).
- The key mark (After Effects' stopwatch-and-diamond in one): no keys -> `key.add` at the playhead with the value shown
  (start animating); keys but none at the playhead -> `key.add` there (a key at a new moment); a key at the playhead ->
  `key.remove` of that key only. Stopping all of a field's animation is its own named action (`stop=True`: `key.clear`,
  keeping the value at the playhead), never a side effect of a click.
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
        self._by_prop = (None, None, {})     # (owner, its keys list, {prop: its keys}): _keys

    def _keys(self, item: dict, prop: str) -> list[dict]:
        """keys_of, with the owner's keys sorted out by field once: the panel asks every row of one owner in turn (a
        scan of all its keys per row). The screen reads finished document states, never changed in place."""
        owner, keys, by = self._by_prop
        if owner is not item or keys is not item.get("keys"):
            by = {}
            for k in item.get("keys", ()):
                by.setdefault(k.get("prop"), []).append(k)
            self._by_prop = (item, item.get("keys"), by)
        return keys_of({"keys": by[prop]}, prop) if prop in by else []

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
        keys = self._keys(item, prop)
        if not keys:
            return "still"
        return "onkey" if key_at(keys, t, fps) else "keyed"

    def animate_calls(self, item: dict, prop: str, t: float, fps: float, stop: bool = False) -> tuple[list[dict], str]:
        """(calls, history label) for a click on the key mark (module doc), or with `stop` for Stop animating."""
        label, keys = self.F.param(item["type"], prop).label, keys_of(item, prop)
        if stop:
            return ([{"op": "key.clear", "target": [item["id"]], "args": {"prop": prop, "at": t}}] if keys else []),                 f"Stop animating {label}"
        if here := key_at(keys, t, fps):
            return [{"op": "key.remove", "target": [here["id"]], "args": {}}], f"Delete {label} key at {t:.2f} s"
        call = self.value_call(item, prop, self.value_at(item, prop, t), t)
        call["op"] = "key.add"
        call["args"]["t"] = call["args"].pop("at")
        return [call], f"Key {label} at {t:.2f} s" if keys else f"Animate {label}"


def key_at(keys: list[dict], t: float, fps: float) -> dict | None:
    """The key at the playhead: within half a frame of t (what the key mark shows filled)."""
    return next((k for k in keys if abs(k["t"] - t) < 0.5 / fps), None)
