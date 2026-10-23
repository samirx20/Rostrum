"""Rostrum2D's hooks into the kit's DocBridge: the 2D animation model (route.py, exprs.py). A mix-in for Bridge2D."""
from __future__ import annotations

from rostrum2d import fields as F

from . import beat_words, exprs, outline, fill_rows, route, size_rows, soundtrack_rows, swap_rows

SIBLING_PICKS = {"matte": lambda s: True,                          # any layer beside it can be its track matte
                 "pathLayer": lambda s: s.get("type") == "path",   # text follows a path layer beside it
                 "ridePath": lambda s: s.get("type") == "path" and not s.get("ridePath")}   # a layer rides one (not a riding one)


# A group's and a rig's box is their children's space, not a size to set; a text's words are typed on the canvas only.
ON_PAGE = {"group": {"w", "h"}, "rig": {"w", "h"}, "text": {"body"}}


class Hooks2D:
    def label_of(self, item):
        owner = self.doc.item(self.doc.parent_of(item["id"])[0]) if item.get("type") == "key" else None
        return outline.label_of(item, owner, owner and (lambda t: beat_words.say(self, t + self.offset(owner["id"]))))

    def kind_label(self, item):          # the panel's subtitle and Ctrl+K hints: "Scene", never the raw "Comp"
        return F.LABELS.get(item.get("type", ""), super().kind_label(item))

    def subtitle(self, item):            # a camera is named "Camera": its line says whose it is, not the name again
        return "Scene camera" if item.get("type") == "camera" else super().subtitle(item)

    def selection_label(self, ids):      # several selected: "2 layers" (any other mix: the kit's "N items")
        if len(ids) > 1 and all(self.doc.item(i)["type"] in F.LAYERS for i in ids):
            return f"{len(ids)} layers"
        return super().selection_label(ids)

    def on_page(self, item):             # fields the screen shows elsewhere (agents still set them through the operation)
        return ON_PAGE.get(item.get("type"), set()) | super().on_page(item)

    def edit_call(self, item_id, param, value):
        if param == size_rows.ROW and self.doc.item(item_id)["type"] == "comp":      # Scene settings › Size: comp.size
            return size_rows.call(item_id, value)
        if param == fill_rows.ROW:                       # the Fill row's paint: layer.fill (fill_rows.py)
            return fill_rows.call(item_id, value, self.own_t(item_id))
        if param == "fillType":                          # the Fill type choice: layer.fill, which also gives a gradient its stops
            return {"op": "layer.fill", "target": [item_id], "args": {"type": value}}
        if param == "ridePath":                          # Rides path: the agents' layer.ride (X, Y become the offset: 0)
            it = self.doc.item(item_id)
            return {"op": "layer.ride", "target": [item_id], "args": {"path": value, "at": it.get("rideAt", "end"),
                    "along": it.get("rideAlong", 0.0), "turn": it.get("rideTurn", False)}}
        if isinstance(value, str) and value.lstrip().startswith("="):    # typed "=pulse()" into a field: the expr.set agents call
            return exprs.typed_call(item_id, param, value)
        return route.edit_call(self.doc, item_id, param, swap_rows.edit_value(self.doc.item(item_id), param, value), self.own_t(item_id))

    def _rows(self):          # a swap set's "Shows" is a choice among its children (swap_rows.py); the scene's
        item = self.doc.item(self._sel) if self._sel else None     # Soundtrack among the project's Sound items
        return fill_rows.rows(size_rows.rows(soundtrack_rows.rows(swap_rows.rows(super()._rows(), item, self._t), item, self.doc.folder), item),
                              item and self.placed_item(item["id"]), self._t, self.comp()["fps"], self._kit.search)   # placed: keys on a marker read

    def shown_values(self, item):
        return route.shown_values(self.placed_item(item["id"]), self._t)     # keys on a marker read as seconds

    def anim_state(self, item, param):
        if param == fill_rows.ROW:                       # the Fill row's mark: its colour's or its stops' keys
            return fill_rows.anim_state(item, self.own_t(item["id"]), self.comp()["fps"])
        return route.anim_state(self.placed_item(item["id"]), param, self._t, self.comp()["fps"])

    def animate_calls(self, item_id, param):
        if param == fill_rows.ROW:
            return fill_rows.animate_calls(self.doc.item(item_id), self.own_t(item_id))
        calls, label = route.animate_calls(self.placed_item(item_id), param, self._t)      # built in composition seconds
        off = self.offset(item_id)
        for c in calls:                                  # the document writes the layer's own seconds
            for k in ("at", "t"):
                if k in c["args"]:
                    c["args"][k] -= off
        return calls, label
    def list_choices(self, item, param):   # the picks (control "pick"): a shared marker by name, or a sibling layer
        if param in ("marker", "endMarker"):
            return [{"value": m["name"], "label": m["name"]} for m in (self.marks.rows() if self.marks else [])]
        if param == "textStyle":                     # the document's text styles (rostrum2d/text_styles.py)
            return [{"value": s["id"], "label": s["name"]} for s in self.doc.data.get("textStyles", [])]
        if param not in SIBLING_PICKS:
            return []
        parent, key, _ = self.doc.parent_of(item["id"])
        return [{"value": s["id"], "label": outline.label_of(s, None)} for s in self.doc.item(parent).get(key, [])
                if s["id"] != item["id"] and SIBLING_PICKS[param](s)]

    def expr_state(self, item, param):
        return exprs.state(item, param)

    def clear_expr_calls(self, item_id, param):
        return exprs.clear_calls(self.doc.item(item_id), param)
