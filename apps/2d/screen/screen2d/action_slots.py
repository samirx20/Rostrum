"""The screen's side of Rostrum2D's action list (actions.py): one kit ActionHub (rostrum_gui/action_hub.py, read in
QML as `backend.actions`) feeds the context bar, the right-click menus, Ctrl+K's "Do" group and the keys, so they
agree and only offer what the selection allows. Each action is one change (its operations in one batch = one undo
step) and what it made is selected after. A slot mix-in for Bridge2D (layer_order.py has the selection it reads)."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui import commands
from rostrum_gui.action_hub import ActionHub
from rostrum_gui.action_views import commands as do_commands
from rostrum_gui.parts import SlotMixin
from rostrum_gui.selection_rules import esc_step

from .action_rules import said
from .actions import LIST, Facts

# What actions.py covers, as the kit's operation commands would list it again in Ctrl+K.
COVERED = ("group.make", "group.release", "rig.make", "mask.make", "mask.release", "shape.boolean", "path.boolean",
           "layer.align", "layer.distribute", "layer.match_size", "style.apply", "layer.lock", "layer.unlock",
           "layer.hide", "layer.remove", "layer.duplicate", "style.define", "style.use", "style.detach")
MAKES = ("group.make", "rig.make", "mask.make", "shape.boolean")        # operations that make a layer: it is selected after


class ActionSlots(SlotMixin):
    # Bridge2D has `renameRequested = Signal(str)`: the Layers panel opens its name box for that layer
    _copied = ""                                    # the layer whose style Paste style puts on others (screen state)

    def _make_actions(self):
        """The one ActionHub, fresh on every selection and document change."""
        self._hub = ActionHub(LIST, self._facts, self._what, self._act_apply, self._act_do, self._set_status, self)
        self.selectionChanged.connect(self._hub.refresh)
        self.docChanged.connect(self._hub.refresh)
        self._keys.changed.connect(self._hub.refresh)       # Ease's keys (F9 …) follow the keys picked
        self._hub.refresh()

    def _facts(self) -> Facts:
        return Facts(self.doc, self.selected_layers(), {"at": self.own_t, "copied": self._copied, "keys": self._keys.ids,
                                                         "sound": self._soundtrack.present, "picked": list(self._kit.selection),
                                                         "clipboard": bool(self.keys_copied() or self._clip_text() or self._strokes.has_clip())})

    def _what(self, f) -> str:
        """What the bar acts on: "title", "3 layers" ("" = nothing selected: no bar)."""
        return self.selection_label(f.ids) if f.ids else ""

    # ---- running an action --------------------------------------------------------------------------------------
    def _act_apply(self, calls, label):
        """An action's calls as one change, then select what it made (a new group, a taken-apart group's layers,
        the copies)."""
        layers = self.selected_layers()
        after = [k["id"] for c in calls if c["op"] == "group.release" for g in c["target"]
                 for k in self.doc.item(g).get("layers", [])]
        after += [c["args"]["id"] for c in calls if c["op"] in MAKES and c["args"].get("id")]
        if not self._guard(lambda: self._apply(calls, label)):
            return
        if said(calls, label, self.doc) != label:      # K: "Keyed 4 settings on 3 layers" (action_rules.said)
            self._set_status(said(calls, label, self.doc))
        if any(c["op"] == "layer.duplicate" for c in calls):
            after = [self.doc.item(parent)[k][at + 1]["id"] for parent, k, at in (self.doc.parent_of(i) for i in layers)]
        if after:
            self.selectMany(after)

    def _act_do(self, name, entry):
        """2D's actions that are not operations by themselves."""
        if name == "rename":
            self.renameRequested.emit(self.selected_layers()[0])
        elif name == "clip_copy" and self._strokes.count:                # strokes picked while painting: those (stroke_select.py)
            self._strokes.copy()
        elif name in ("clip_copy", "clip_cut") and self._keys.count:     # keys picked: their keys (key_edits.py)
            (self.copyKeys if name == "clip_copy" else self.cutKeys)()
        elif name == "paste" and not self.keys_copied() and self._strokes.has_clip():   # strokes copied (stroke_select.py)
            self._strokes.paste()
        elif name == "paste" and self.keys_copied():
            self.pasteKeys()
        elif name in ("clip_copy", "clip_cut", "paste"):
            {"clip_copy": self.copyLayers, "clip_cut": self.cutLayers, "paste": self.pasteLayers}[name]()
        elif name == "stagger":
            self._stagger.start()
        elif name == "depth":                                            # Set depth ▾ › Other depth… (depth_typed.py)
            self._depth_typed.start()
        elif name == "sound_here":
            self._cuepick.start()
        elif name in ("lipsync", "blinks"):                              # the character sheets (rig_lipsync.py, rig_blinks.py)
            (self._lipsync if name == "lipsync" else self._blinks).start()
        elif name == "copy_style":
            self._copied = self.selected_layers()[0]
            self._set_status(f"Copied the style of {self.label_of(self.doc.item(self._copied))}")
        else:
            raise ValueError(f'action {entry["id"]}: Rostrum2D has no "{name}" action')

    # ---- the doors QML and scripts call -------------------------------------------------------------------------
    def _commands(self):
        """Ctrl+K: the actions first (the same list as the bar and the menus), then the kit's commands they don't
        repeat."""
        out = [c for c in super()._commands() if not any(c["key"] == o or c["key"].startswith(o + ":") for o in COVERED)]
        f = self._facts()
        mine = [{**c, "do": lambda k=c["key"]: self._hub.run(k)} if "do" in c else c
                for c in do_commands(LIST.available(f), self._what(f))]
        return mine + [{"key": "layer:selectall", "label": "Select all layers", "hint": "Layer", "keys": "Ctrl+A",
                        "do": self.selectAllLayers}] + out

    @Slot(str, result="QVariantList")
    def commands(self, query):
        found = [{k: c.get(k, "") for k in ("key", "label", "hint", "keys")} for c in commands.search(self._commands(), query)]
        return found + self._whys(query, found)

    def _whys(self, query, found) -> list[dict]:
        """Ctrl+K: an action typed by name (its label or the bar button it sits under) that this selection doesn't allow
        and that has its own sentence (`why`) shows it, so the person learns why it is absent; choosing it says it again."""
        q, f = query.strip().lower(), self._facts()
        have = {c["key"] for c in found}
        why = next(((a.id, LIST._sentence(a, f)) for a in LIST.actions if len(q) >= 3 and a.id not in have and a.why
                    and q in f"{a.bar} {a.label_for(f)}".lower() and LIST._sentence(a, f)), None)
        return [{"key": why[0], "label": why[1], "hint": "Not available now", "keys": ""}] if why else []

    @Slot(str, result=bool)
    def run(self, key):
        """Ctrl+K, a menu or a script: an action of the list through the hub (one change), else the kit's."""
        if not LIST.owns(key):
            return super().run(key)
        entry = next((e for e in LIST.available(self._facts()) if e["id"] == key), None)
        self._hub.run(key)                          # not valid now: the hub says why in the status
        return entry is not None

    @Slot(str, result=bool)
    def layerCommand(self, how):
        """A key's or a script's action by job (front, delete, group …): runs if valid now, else says why. Keys picked
        in the timeline take Delete first (key_select.py)."""
        if how in ("delete", "layer:delete") and self._keys.count:
            return self._keys.remove()
        if how in ("delete", "layer:delete") and self._stretch.shown:     # a picked stretch: its animation (stretch_select.py)
            return self._stretch.remove()
        entry, why = LIST.on_key(self._facts(), how)
        if entry is None:
            if why:
                self._set_status(why)
            return False
        self._hub.run(entry["id"])
        return True

    @Slot(result="QVariantList")
    def actionMenu(self):
        return self._hub.menu()

    @Slot(str, result="QVariantList")
    def layerMenu(self, layer_id):
        """A layer's right-click (its row, or the canvas under the pointer): an unselected layer is selected alone
        first, a selected one keeps the selection; then the menu for the selection."""
        if layer_id and layer_id not in self.selected_layers():
            self.select(layer_id)
        return self.actionMenu()

    @Slot("QVariantMap", result=str)
    def stepBack(self, state):
        """Esc: the one step the kit's ladder takes now (selection_rules.esc_step). "cancel" and "close" are the
        screen's own (it closes its panel or menu); "clear" clears the selection here."""
        step = esc_step({**state, "inner": bool(self._keys.count or self._stretch.shown), "selected": bool(self.selected_layers())})
        if step == "clear_inner":                   # keys picked in the timeline go first, the layer stays picked
            layer = self.selected_layers()
            self._keys.clear()
            self._stretch.clear()                   # a picked stretch goes back to its layer the same way
            self.selectMany(layer)
        elif step == "clear":
            self.clearSelection()
        return step or ""
