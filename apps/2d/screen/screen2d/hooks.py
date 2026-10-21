"""Rostrum2D's hooks into the kit's DocBridge: the 2D animation model (route.py, exprs.py). A mix-in for Bridge2D."""
from __future__ import annotations

from . import exprs, outline, route, swap_rows


class Hooks2D:
    def label_of(self, item):
        owner = self.doc.item(self.doc.parent_of(item["id"])[0]) if item.get("type") == "key" else None
        return outline.label_of(item, owner)

    def edit_call(self, item_id, param, value):
        return route.edit_call(self.doc, item_id, param, swap_rows.edit_value(self.doc.item(item_id), param, value), self._t)

    def _rows(self):          # a swap set's "Shows" is a choice among its children (swap_rows.py)
        return swap_rows.rows(super()._rows(), self.doc.item(self._sel) if self._sel else None, self._t)

    def shown_values(self, item):
        return route.shown_values(self.placed_item(item["id"]), self._t)     # keys on a marker read as seconds

    def anim_state(self, item, param):
        return route.anim_state(self.placed_item(item["id"]), param, self._t, self.comp()["fps"])

    def animate_calls(self, item_id, param):
        return route.animate_calls(self.placed_item(item_id), param, self._t)

    def expr_state(self, item, param):
        return exprs.state(item, param)

    def clear_expr_calls(self, item_id, param):
        return exprs.clear_calls(self.doc.item(item_id), param)
