"""The selected layers as the actions read them, and the layer edits that are not actions: the rows' lock and eye,
the keyboard's select all, clear and nudge, and the Layers list's drag-to-reorder and rename. The actions on the
selection (Group, Mask, Delete …) are action_slots.py's. A slot mix-in for Bridge2D."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum2d.evaluate import resolve
from rostrum_core.tree import subtree_ids
from rostrum_gui.parts import SlotMixin

from . import bounds, levels, route


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

    @Slot(result="QVariantMap")
    def selectionExtent(self) -> dict:
        """x0, y0, x1, y1 (composition px) round the selected layers' outlines as the picture shows them; {} for none
        (F: fit the selection, Stage.qml)."""
        es = [bounds.extent(b) for b in self._multi.boxes]
        return {"x0": min(e[0] for e in es), "y0": min(e[1] for e in es), "x1": max(e[2] for e in es), "y1": max(e[3] for e in es)} if es else {}

    @Slot(str, str, result=bool)
    def toggleSwitch(self, layer_id, which):
        """The lock or the eye on a layer's row (which: "locked" | "hidden"): that layer only, one change."""
        item = self.doc.item(layer_id)
        now = bool(item.get(which))
        label = {"locked": ("Lock", "Unlock"), "hidden": ("Hide", "Show")}[which][now]
        return self._guard(lambda: self._apply(self._switch_calls([layer_id], which, not now), f"{label} {self.label_of(item)}"))

    def _above(self, layer_id):
        """The layers a layer sits inside, nearest first."""
        out, i = [], layer_id
        while self.doc.has(i) and (p := self.doc.parent_of(i)[0]) is not None and self.doc.has(p) and self.doc.item(p)["type"] in self._layer_types():
            out.append(p)
            i = p
        return out

    def _switch_calls(self, ids, which, on):
        """The calls that put the lock / eye of every layer of `ids` to `on` (the ones already there change nothing).
        Locks go innermost first and unlocks outermost first (a layer inside a locked group can't be changed); the eye of
        a locked layer, or of one inside a locked group, is left as it is (an operation may not change it)."""
        deep = {i: len(self._above(i)) for i in ids}
        calls = []
        for i in sorted(ids, key=lambda i: -deep[i] if (which == "locked" and on) else deep[i]):
            item = self.doc.item(i)
            if bool(item.get(which)) == on or (which == "hidden" and (item.get("locked") or any(self.doc.item(a).get("locked") for a in self._above(i)))):
                continue
            calls.append({"op": "value.set", "target": [i], "args": {"prop": "locked", "v": on}} if which == "locked" and item["type"] == "camera"
                         else {"op": ("layer.lock" if on else "layer.unlock"), "target": [i], "args": {}} if which == "locked"
                         else {"op": "layer.hide", "target": [i], "args": {"on": on}})
        return calls

    @Slot("QStringList", str, bool, result=bool)
    def setSwitches(self, ids, which, on):
        """Press the lock or the eye and drag over more rows (LayerRows.qml): every row passed gets the first row's new
        state, ONE change on release (one Ctrl+Z puts them all back)."""
        calls = self._switch_calls(ids, which, on)
        if not calls:
            return False
        noun = {"locked": ("Lock", "Unlock"), "hidden": ("Hide", "Show")}[which][not on]
        return self._guard(lambda: self._apply(calls, f"{noun} {len(calls)} layers"))

    @Slot(str, result=bool)
    def soloLayer(self, layer_id):
        """Alt+click an eye: show only this layer at its level (the others there hidden); Alt+click it again brings back
        only the ones it hid. One change each. What it hid is kept until those layers are shown again by anything."""
        doc, hit = self.doc, self.doc.kind.registry.get("layer.hide").targets
        parent = doc.parent_of(layer_id)[0]
        others = [c["id"] for c in doc.item(parent)["layers"] if c["id"] != layer_id and c["type"] in hit]
        back = [i for i in getattr(self, "_soloed", {}).get(layer_id, []) if doc.has(i) and doc.item(i).get("hidden")]
        if back and not doc.item(layer_id).get("hidden"):
            calls, label = self._switch_calls(back, "hidden", False), "Show the layers hidden by Show only"
        else:
            hid = [i for i in others if not doc.item(i).get("hidden")]
            calls = self._switch_calls(hid, "hidden", True) + self._switch_calls([layer_id], "hidden", False)
            label = f"Show only {self.label_of(doc.item(layer_id))}"
            self._soloed = {layer_id: hid}
        if not calls:
            return False
        return self._guard(lambda: self._apply(calls, label))

    # ---- keyboard: select all, clear, nudge ---------------------------------------------------------------------
    @Slot()
    def selectAllLayers(self):
        """Ctrl+A: every layer at the level you are in (levels.py: the group's layers once inside one, else the
        composition's; not the camera). The rows and outlines light at once; the status line then says how many
        (a stand-in for the kit's acknowledgement line, not in main yet)."""
        ids = levels.level_of(self.doc, self.selected_layers(), self.comp_id)
        if ids:
            self._select(ids)
            self._set_status(f"Picked {len(ids)} layer{'' if len(ids) == 1 else 's'}")

    @Slot()
    def clearSelection(self):
        self.select(self.comp_id)

    @Slot(float, float, result=bool)
    def nudge(self, dx, dy):
        """An arrow key: every selected layer moves (px, in its parent's px) at the playhead (an animated x / y gets a
        key there). One change per press (never joined to the one before); a locked layer, or one an auto layout or expression
        places, refuses loudly."""
        layers = self.selected_layers()
        if not layers:
            return False
        calls = []
        for lay in layers:
            item, t = self.doc.item(lay), self.own_t(lay)
            now = resolve(item, t)
            calls += [route.value_call(item, p, round(now[p] + d, 2), t) for p, d in (("x", dx), ("y", dy)) if d]
        label = f"Nudge {self.label_of(self.doc.item(layers[0]))}" if len(layers) == 1 else f"Nudge {len(layers)} layers"
        return self._guard(lambda: self._done(self.doc.apply(calls, self.who, label=label, join=False), ""))

    # ---- the Layers list ------------------------------------------------------------------------------------------
    @Slot(str, str, str, result=bool)
    def moveLayer(self, layer_id, target_id, where):
        """Drag-to-reorder in the Layers panel: put the layer above / below the target row, or (a group) inside it on top.
        One layer.arrange = one undo step; dropping on itself or inside itself changes nothing. (A person's row drag is
        the same call inside its gesture: row_drag.py.)"""
        call = self.arrange_call(layer_id, target_id, where)
        return call is not None and self._guard(lambda: self._apply([call], f"Move {self.label_of(self.doc.item(layer_id))}"))

    def arrange_call(self, layer_id, target_id, where):
        """The layer.arrange that puts the layer above / below / into the target row, or None when it changes nothing."""
        doc = self.doc
        if layer_id == target_id or not (doc.has(layer_id) and doc.has(target_id)):
            return None
        types = self._layer_types()
        if doc.item(layer_id)["type"] not in types or doc.item(target_id)["type"] not in types:
            return None
        if where == "into":
            if doc.item(target_id)["type"] not in ("group", "rig"):
                return None
            into, rest = target_id, [c["id"] for c in doc.item(target_id)["layers"] if c["id"] != layer_id]
            at = len(rest)
        else:
            into = doc.parent_of(target_id)[0]
            rest = [c["id"] for c in doc.item(into)["layers"] if c["id"] != layer_id]
            at = rest.index(target_id) + (1 if where == "above" else 0)       # the panel lists the top of the stack first
        if into == layer_id or into in subtree_ids(doc.item(layer_id), doc.kind.lists):
            return None
        if into == doc.parent_of(layer_id)[0] and rest[:at] + [layer_id] + rest[at:] == [c["id"] for c in doc.item(into)["layers"]]:
            return None                                                      # dropped where it already is
        return {"op": "layer.arrange", "target": [layer_id], "args": {"into": into, "index": at}}

    @Slot(str, str, result=bool)
    def renameLayer(self, layer_id, name):
        """The Layers panel's name box: item.rename, one change (an empty name changes nothing)."""
        name = name.strip()
        if not name or name == self.doc.item(layer_id).get("name"):
            return False
        return self._guard(lambda: self._apply([{"op": "item.rename", "target": [layer_id], "args": {"name": name}}],
                                               f"Rename {self.label_of(self.doc.item(layer_id))}"))
