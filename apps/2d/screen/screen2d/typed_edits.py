"""A number typed in the settings panel, 2D's way (a slot mix-in for Bridge2D; the kit's EditSlots.setValue underneath):
- X or Y with several layers picked moves them together, as Figma does: the leftmost (topmost) one lands on the typed
  value and every other moves by the same amount, so their spacing stays (each layer's `value.set {by}`, the call an
  agent makes; one change). Every other field sets the typed value on each of them, as before.
- A typed half of a two-value setting keeps keys only where they change (pair_keys.py).
"""
from __future__ import annotations

from PySide6.QtCore import Slot

from rostrum_gui.parts import SlotMixin

from . import pair_keys

MOVES = ("x", "y")


class TypedEdits(SlotMixin):
    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        number = isinstance(value, (int, float)) and not isinstance(value, bool)
        ids = self._targets(param) if number else []
        if param in MOVES and len(ids) > 1:
            return self._move_together(param, float(value), ids)
        if number and pair_keys.partner(param) and ids:
            return self._guard(lambda: self._apply(
                [c for i in ids for c in pair_keys.typed_calls(self.doc.item(i), param, value, self.own_t(i), self.edit_call(i, param, value))],
                self._many(self._edit_label(ids[0], param, value), len(ids))))
        return super().setValue(param, value)

    def _move_together(self, param, value, ids):
        now = {i: self.shown_values(self.doc.item(i)).get(param) for i in ids}
        if not all(isinstance(v, (int, float)) for v in now.values()):
            return super().setValue(param, value)
        by = value - min(now.values())
        calls = [c for c in (self.relative_call(i, param, by, 1) for i in ids) if c]
        if len(calls) < len(ids):        # one can't move (driven by an expression or a layout): none is moved alone
            return super().setValue(param, value)
        label = f"Move {len(ids)} layers to {param.upper()} {value:g}"
        return self._guard(lambda: self._apply(calls, label))
