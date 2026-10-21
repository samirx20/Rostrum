"""Turning a screen edit into an operation call: the call itself, what the history calls it, and the scrub
gesture (press-drag-release = one change). Pure helpers over rostrum_core; no Qt."""
from __future__ import annotations

from rostrum_core import RostrumError, codes


def field_param(doc, item_id, name):
    op = doc.kind.registry.field_op(doc.item(item_id)["type"])
    if op is None:
        raise RostrumError(codes.UNKNOWN_OPERATION, "inspector", f'"{item_id}"', "has no settings operation")
    return op, op.param(name)


def field_call(doc, item_id, name, value) -> dict:
    """{"op": "<kind>.set", "target": [item], "args": {name: value}}; numbers from QML come as floats,
    so whole-number params get ints. Range and type checks are the operation's own (it fails loudly)."""
    op, p = field_param(doc, item_id, name)
    if p is not None and p.type == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
        value = int(round(value)) if p.integer else round(float(value), 6)
    return {"op": op.name, "target": [item_id], "args": {name: value}}


def edit_label(doc, item_id, name, value) -> str:
    """What the history says: "Turn on Depth of field", "Type: Spot", "Change Focal length"."""
    _, p = field_param(doc, item_id, name)
    label = p.label if p else name
    if p is not None and p.type == "toggle":
        return f"Turn {'on' if value else 'off'} {label}"
    if p is not None and p.type == "choice":
        return f"{label}: {value}"
    return f"Change {label}"


class Scrub:
    """One drag on a number or slider: begin, preview each move, end (one change) or cancel (nothing)."""

    def __init__(self, doc, who, item_id, name):
        self.doc, self.item_id, self.name = doc, item_id, name
        self._ctx = doc.gesture(edit_label(doc, item_id, name, None), who)
        self._ctx.__enter__()              # a second open drag raises CONFLICT

    def preview(self, value):
        self._ctx.preview([field_call(self.doc, self.item_id, self.name, value)])

    def end(self, cancel=False):
        if cancel:
            self._ctx.cancel()
        self._ctx.__exit__(None, None, None)
        return self._ctx.change
