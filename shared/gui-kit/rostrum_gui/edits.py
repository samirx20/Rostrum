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
        return f"{label}: {p.option_label(value)}"
    return f"Change {label}"


class Drag:
    """One press-drag-release = one change: preview each move's calls, then end (one change) or cancel (nothing)."""

    def __init__(self, doc, who, label):
        self._ctx = doc.gesture(label, who)
        self._ctx.__enter__()              # a second open drag raises CONFLICT

    def preview(self, calls, fresh=False):
        """`fresh`: on the state from before the drag, not on top of the last step (Gesture.preview)."""
        self._ctx.preview(calls, fresh)

    def end(self, cancel=False, calls=None, label=None):
        """Close the drag: one change, or nothing with `cancel`; `label`: what the history calls it, decided at the end
        (the amounts popover's "Humanise · 12 notes · 15 ms, 8 %"). `calls`: a last preview first (the whole gesture at
        once, as a wet stroke gives it); if it is refused the drag still closes, with nothing, and the refusal goes on.
        A drag left open would refuse every later edit ("being dragged by a person")."""
        if calls is not None and not cancel:
            try:
                self._ctx.preview(calls)
            except BaseException:
                self._ctx.cancel()
                self._ctx.__exit__(None, None, None)
                raise
        if cancel:
            self._ctx.cancel()
        if label:
            self._ctx.label = label
        self._ctx.__exit__(None, None, None)
        return self._ctx.change


class Scrub(Drag):
    """One drag on a number or slider. `call(item_id, name, value)` makes each move's call (default field_call;
    an app with keys routes it through its own value operation). `item_id`: one item, or a list (every selected
    item moves to the same value; still one change)."""

    def __init__(self, doc, who, item_id, name, call=None):
        self.items = [item_id] if isinstance(item_id, str) else list(item_id)
        label = edit_label(doc, self.items[0], name, None)
        super().__init__(doc, who, label if len(self.items) == 1 else f"{label} on {len(self.items)} items")
        self.item_id, self.name = self.items[0], name
        self._call = call or (lambda i, n, v: field_call(doc, i, n, v))

    def preview(self, value):
        if getattr(self, "_shown", None) == (value,):     # the pointer moved but the value didn't (a release on the
            return                                        # last move's place): nothing to plan, tell or draw again
        super().preview([self._call(i, self.name, value) for i in self.items])
        self._shown = (value,)
