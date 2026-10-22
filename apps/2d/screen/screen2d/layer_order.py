"""The screen's side of the one list of actions on selected layers (actions.py): the right-click menus, the action bar,
Ctrl+K and the shortcuts (Group, Mask, Align, Lock, Delete, Bring forward, Rename …) all read it, so they agree and
only offer what the selection allows. Each action is one change: its operations in one batch = one undo step. Also the
keyboard's select all, clear and nudge, and the Layers list's drag-to-reorder and rename. A slot mix-in for Bridge2D."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum2d.evaluate import resolve
from rostrum_core.tree import subtree_ids
from rostrum_gui.parts import SlotMixin

from . import bounds, route
from .actions import available

# What actions.py covers, as the kit's operation commands would list it again in Ctrl+K.
COVERED = ("group.make", "group.release", "rig.make", "mask.make", "mask.release", "shape.boolean", "path.boolean",
           "layer.align", "layer.distribute", "layer.match_size", "style.apply", "layer.lock", "layer.unlock",
           "layer.hide", "layer.remove", "layer.duplicate")
MAKES = ("group.make", "rig.make", "mask.make", "shape.boolean")        # operations that make a layer: it is selected after


class LayerOrder(SlotMixin):
    # Bridge2D has `renameRequested = Signal(str)`: the Layers panel opens its name box for that layer
    _copied = ""                                    # the layer whose style Paste style puts on others (screen state)

    # ---- the selection (the one place that reads it) ------------------------------------------------------------
    def selected_layers(self) -> list[str]:
        """The selected layers, the primary first: the kit's selection (`selection`) with whatever else the canvas's
        Shift+click holds (multi.py). When the kit's selection holds them all, delete the `_multi` part."""
        types, out = self._layer_types(), []
        for i in [*(getattr(self, "selection", None) or []), *self._multi.extras()]:
            layer = bounds.layer_of(self.doc, i) if self.doc.has(i) else ""
            if layer and layer not in out and self.doc.item(layer)["type"] in types:
                out.append(layer)
        return out

    def _select(self, ids: list[str]):
        self._multi._set(ids)           # the outlines on the canvas read multi.py ...
        self.selectMany(ids)            # ... and the kit's selection (the settings panel, Ctrl+K) reads this

    def _layer_types(self):
        return self.doc.kind.registry.get("layer.remove").targets

    # ---- the list ---------------------------------------------------------------------------------------------------
    def _actions(self) -> list[dict]:
        return available(self.doc, self.selected_layers(), {"at": self.own_t, "copied": self._copied})

    def _layer_commands(self) -> list[dict]:
        return [{**a, "hint": f"Layer ({a['shortcut']})" if a["shortcut"] else "Layer"} for a in self._actions()]

    def _commands(self):
        out = [c for c in super()._commands() if not any(c["key"] == o or c["key"].startswith(o + ":") for o in COVERED)]
        return self._layer_commands() + [self._select_all_command()] + out

    @staticmethod
    def _select_all_command() -> dict:
        return {"key": "layer:selectall", "label": "Select all layers", "hint": "Layer (Ctrl+A)", "calls": [], "do": "selectall"}

    @staticmethod
    def _entry(a: dict) -> dict:
        return {"value": a["key"], "label": a["label"], "hint": a["shortcut"], "group": a["group"]}

    @Slot(str, result="QVariantList")
    def layerMenu(self, layer_id):
        """The right-click menu of a layer row: selects it (unless it is already picked), then lists what applies."""
        if layer_id not in self.selected_layers():
            self.select(layer_id)
        return self.actionMenu()

    @Slot(result="QVariantList")
    def actionMenu(self):
        """Every action the selection allows, in menu order: [{value, label, hint (shortcut), group (a divider between groups)}]."""
        return [self._entry(a) for a in self._actions()]

    @Slot(result="QVariantList")
    def actionBar(self):
        """The action bar's buttons: [{key, label, shortcut, menu}], most used first; `menu` lists a button's choices
        (Boolean, Align, Distribute) and is empty for a button that acts at once."""
        items = []
        for a in (x for x in self._actions() if x["importance"] == "bar"):
            name = a["bar"] or a["label"]
            item = next((i for i in items if i["label"] == name), None)
            if item is None:
                item = {"key": "" if a["bar"] else a["key"], "label": name, "shortcut": a["shortcut"], "menu": []}
                items.append(item)
            if a["bar"]:
                item["menu"].append(self._entry(a))
        return items

    @Slot(result="QVariantMap")
    def selectionExtent(self) -> dict:
        """x0, y0, x1, y1 (composition px) round the selected layers' outlines as the picture shows them; {} for none."""
        es = [bounds.extent(b) for b in self._multi.boxes]
        return {"x0": min(e[0] for e in es), "y0": min(e[1] for e in es), "x1": max(e[2] for e in es), "y1": max(e[3] for e in es)} if es else {}

    @Slot(str, result=bool)
    def run(self, key):
        if key == "layer:selectall":
            self.selectAllLayers()
            return True
        cmd = next((c for c in self._layer_commands() if c["key"] == key), None) if key.startswith("layer:") else None
        if cmd is None:
            return super().run(key)
        if cmd["do"] == "rename":
            self.renameRequested.emit(self.selected_layers()[0])
            return True
        if cmd["do"] == "copy":
            self._copied = self.selected_layers()[0]
            self._set_status(f"Copied the style of {self.label_of(self.doc.item(self._copied))}")
            return True
        layers = self.selected_layers()
        after = self._after(cmd, layers)
        if not super().run(key):
            return False
        if cmd["key"] == "layer:duplicate":
            after = [self.doc.item(parent)[k][at + 1]["id"] for parent, k, at in (self.doc.parent_of(i) for i in layers)]
        if after:
            self._select(after)
        return True

    def _after(self, cmd: dict, layers: list[str]) -> list[str]:
        """What is selected once the action is done: a layer it made, or a taken-apart group's layers."""
        if cmd["key"] == "layer:ungroup":
            return [k["id"] for g in layers for k in self.doc.item(g).get("layers", [])]
        return [c["args"]["id"] for c in cmd["calls"] if c["op"] in MAKES and c["args"].get("id")]

    @Slot(str, result=bool)
    def layerCommand(self, how):
        """A shortcut's command (front, back, forward, backward, delete, rename, group, ungroup …): the same as Ctrl+K's,
        and quiet when it can't apply right now."""
        key = how if how.startswith("layer:") else f"layer:{how}"
        if not any(c["key"] == key for c in self._layer_commands()):
            return False
        return self.run(key)

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
