"""The selected layers as the actions read them, and the layer edits that are not actions: the rows' lock and eye,
the keyboard's select all, clear and nudge, and the Layers list's drag-to-reorder and rename. The actions on the
selection (Group, Mask, Delete …) are action_slots.py's. A slot mix-in for Bridge2D."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum2d.evaluate import resolve
from rostrum_core.tree import subtree_ids
from rostrum_gui.parts import SlotMixin

from . import bounds, route


class LayerOrder(SlotMixin):
    # ---- the selection (the one place that reads it) ------------------------------------------------------------
    def selected_layers(self) -> list[str]:
        """The selected layers, the primary first, from the kit's one selection (`selection`; an effect, mask or key
        counts as its layer)."""
        types, out = self._layer_types(), []
        for i in self.selection:
            layer = bounds.layer_of(self.doc, i) if self.doc.has(i) else ""
            if layer and layer not in out and self.doc.item(layer)["type"] in types:
                out.append(layer)
        return out

    def _select(self, ids: list[str]):
        self.selectMany(ids)            # the one selection (the canvas, the list, the settings panel, Ctrl+K)

    def _layer_types(self):
        return self.doc.kind.registry.get("layer.remove").targets

    @Slot(str, str, result=bool)
    def toggleSwitch(self, layer_id, which):
        """The lock or the eye on a layer's row (which: "locked" | "hidden"): that layer only, one change."""
        item = self.doc.item(layer_id)
        now = bool(item.get(which))
        call = ({"op": "layer.unlock" if now else "layer.lock", "target": [layer_id], "args": {}} if which == "locked"
                else {"op": "layer.hide", "target": [layer_id], "args": {"on": not now}})
        label = {"locked": ("Lock", "Unlock"), "hidden": ("Hide", "Show")}[which][now]
        return self._guard(lambda: self._apply([call], f"{label} {self.label_of(item)}"))

    # ---- keyboard: select all, clear, nudge ---------------------------------------------------------------------
    @Slot()
    def selectAllLayers(self):
        """Ctrl+A: every top-level layer of the composition (not the camera)."""
        ids = [c["id"] for c in reversed(self.comp()["layers"]) if c["type"] != "camera"]
        if ids:
            self._select(ids)

    @Slot()
    def clearSelection(self):
        self.select(self.comp_id)

    @Slot(float, float, result=bool)
    def nudge(self, dx, dy):
        """An arrow key: every selected layer moves (px, in its parent's px) at the playhead (an animated x / y gets a
        key there). One change; a locked layer, or one an auto layout or expression places, refuses loudly."""
        layers = self.selected_layers()
        if not layers:
            return False
        calls = []
        for lay in layers:
            item, t = self.doc.item(lay), self.own_t(lay)
            now = resolve(item, t)
            calls += [route.value_call(item, p, round(now[p] + d, 2), t) for p, d in (("x", dx), ("y", dy)) if d]
        label = f"Nudge {self.label_of(self.doc.item(layers[0]))}" if len(layers) == 1 else f"Nudge {len(layers)} layers"
        return self._guard(lambda: self._apply(calls, label))

    # ---- the Layers list ------------------------------------------------------------------------------------------
    @Slot(str, str, str, result=bool)
    def moveLayer(self, layer_id, target_id, where):
        """Drag-to-reorder in the Layers panel: put the layer above / below the target row, or (a group) inside it on top.
        One layer.arrange = one undo step; dropping on itself or inside itself changes nothing."""
        doc = self.doc
        if layer_id == target_id or not (doc.has(layer_id) and doc.has(target_id)):
            return False
        types = self._layer_types()
        if doc.item(layer_id)["type"] not in types or doc.item(target_id)["type"] not in types:
            return False
        if where == "into":
            if doc.item(target_id)["type"] not in ("group", "rig"):
                return False
            into, rest = target_id, [c["id"] for c in doc.item(target_id)["layers"] if c["id"] != layer_id]
            at = len(rest)
        else:
            into = doc.parent_of(target_id)[0]
            rest = [c["id"] for c in doc.item(into)["layers"] if c["id"] != layer_id]
            at = rest.index(target_id) + (1 if where == "above" else 0)       # the panel lists the top of the stack first
        if into == layer_id or into in subtree_ids(doc.item(layer_id), doc.kind.lists):
            return False
        if into == doc.parent_of(layer_id)[0] and rest[:at] + [layer_id] + rest[at:] == [c["id"] for c in doc.item(into)["layers"]]:
            return False                                                      # dropped where it already is
        return self._guard(lambda: self._apply([{"op": "layer.arrange", "target": [layer_id], "args": {"into": into, "index": at}}],
                                               f"Move {self.label_of(doc.item(layer_id))}"))

    @Slot(str, str, result=bool)
    def renameLayer(self, layer_id, name):
        """The Layers panel's name box: item.rename, one change (an empty name changes nothing)."""
        name = name.strip()
        if not name or name == self.doc.item(layer_id).get("name"):
            return False
        return self._guard(lambda: self._apply([{"op": "item.rename", "target": [layer_id], "args": {"name": name}}],
                                               f"Rename {self.label_of(self.doc.item(layer_id))}"))
