"""The screen's side of Rostrum2D's action list (actions.py): one kit ActionHub (rostrum_gui/action_hub.py, read in
QML as `backend.actions`) feeds the settings panel's actions, the one short right-click menu (canvas, layers list,
timeline: rostrum_gui.actions.SHORT_MENU), Ctrl+K's "Do" group and the keys, so they
agree and only offer what the selection allows. Each action is one change (its operations in one batch = one undo
step) and what it made is selected after. A slot mix-in for Bridge2D (layer_order.py has the selection it reads)."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui import commands, job_rows
from rostrum_gui.action_views import commands as do_commands
from rostrum_gui.parts import SlotMixin
from rostrum_gui.selection_rules import esc_step

from . import frame_actions, job_when, keyed_note
from .action_rules import said
from .actions import LIST, PANEL_TWIN, Facts
from .key_routes import KeyHub
from .keys2d import HAVE_ROWS, KEYS2D, ROUTES, SHELL, WINDOW

# What actions.py covers, as the kit's operation commands would list it again in Ctrl+K.
COVERED = ("group.make", "group.release", "rig.make", "mask.make", "mask.release", "shape.boolean", "path.boolean",
           "layer.align", "layer.distribute", "layer.match_size", "style.apply", "layer.lock", "layer.unlock",
           "layer.hide", "layer.remove", "layer.duplicate", "style.define", "style.use", "style.detach",
           "frame.fit", "frame.cut", "frame.home", "background.fit", "layer.fill_frame")
COVERED_FIELDS = ("locked", "hidden", "screenLock")      # settings whose own toggle an action is (Lock, Hide, Stick to the shot)
UNLISTED = ("key",)                                       # items Ctrl+K never offers to select: keys are picked on the timeline


def _covered(key: str) -> bool:
    """A kit command an action already is: the same operation, or the toggle of a setting an action switches."""
    return any(key == o or key.startswith(o + ":") for o in COVERED) or any(key.endswith(f".set:{f}") for f in COVERED_FIELDS)


TWINS = "layer:" + PANEL_TWIN                                       # the panel's Order ▾ twins: not in Ctrl+K (actions.py)
MAKES = ("group.make", "rig.make", "mask.make", "shape.boolean")        # operations that make a layer: it is selected after


def _needs_unlock(c: dict) -> bool:
    """A kit command that changes the picked locked layer (an operation on it, or a field to edit) and so would refuse:
    not the lock switch itself, and not a command on the whole document (it has no target)."""
    calls = c.get("calls") or []
    if c["key"].startswith("field:"):
        return True
    return any(call.get("target") and set(call["args"]) != {"locked"} for call in calls)


class ActionSlots(SlotMixin):
    # Bridge2D has `renameRequested = Signal(str)`: the Layers panel opens its name box for that layer
    _copied = ""                                    # the layer whose style Paste style puts on others (screen state)

    def _make_actions(self):
        """The one ActionHub, fresh on every selection and document change."""
        self._hub = KeyHub(self, LIST, self._facts, self._what, self._act_apply, self._act_do, self._set_status,
                          preview_fn=self._preview_calls, unpreview_fn=self._preview_end)
        self.panelShown.connect(self._hub.refresh)          # the panel's actions and the context bar come with the panel
        self.docChanged.connect(self._hub.refresh_later)   # (an action's own pick then refreshes once: action_hub)
        self._keys.changed.connect(self._hub.refresh)       # Ease's keys (F9 …) follow the keys picked
        for sig in (self.timeChanged, self.playingChanged, self.markersChanged):   # Cut here, Frame home: at the playhead
            sig.connect(self._hub_at)
        self._hub.refresh()

    def _facts(self) -> Facts:
        return Facts(self.doc, self.selected_layers(), {"at": self.own_t, "now": self._t, "copied": self._copied, "keys": self._keys.ids,
                                                         "key_clip": bool(self.keys_copied()),          # Ctrl+Shift+V's words
                                                         "sound": self._soundtrack.present, "picked": list(self._kit.selection),
                                                         "frame": frame_actions.state(self),
                                                         "clipboard": bool(self.keys_copied() or self._clip_text() or self._strokes.has_clip())})

    def _hub_at(self):
        """The playhead or the markers moved: the frame's actions follow in the frame after (not while playing: nothing
        is picked then). Running an action works its facts out afresh, so a key pressed meanwhile sees the playhead."""
        if not self.play.playing:
            self._hub.refresh_later()

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
        if frame_actions.already(calls, self._facts()):          # Frame the view on what the frame shows: keys that change nothing
            self._set_status("Already framed")
            return
        framed = frame_actions.told(calls, self._facts()) if any(c["op"] in frame_actions.OPS for c in calls) else ""   # said before
        made = []
        if not self._guard(lambda: made.append(self._apply(calls, label))):
            return
        if made[0] is None:                                   # K again, Align on what is already aligned: nothing was different
            return                                            # (_apply said so in the top bar)
        words = (framed or said(calls, label, self.doc)) + keyed_note.note(self.doc, made[0], calls, self._t)
        if words != label:                                    # K: "Keyed 4 settings on 3 layers" (action_rules.said); an
            self._set_status(words)                           # Align that keyed X: "… · keyed X at 3.00 s" (keyed_note.py)
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
        elif name in ("paste", "paste_other") and not self.keys_copied() and self._strokes.has_clip():   # strokes copied (stroke_select.py)
            self._strokes.paste()
        elif name in ("paste", "paste_other") and self.keys_copied():   # the latest copy wins: keys (key_edits.py)
            self.pasteKeys("playhead" if name == "paste" else "original")
        elif name in ("clip_copy", "clip_cut", "paste", "paste_other"):  # (keys picked took Copy and Cut already: KeyHub)
            {"clip_copy": self.copyLayers, "clip_cut": self.cutLayers, "paste": self.pasteLayers,
             "paste_other": self.pasteLayers}[name]()
        elif name == "stagger":
            self._stagger.start()
        elif name == "depth":                                            # Set depth ▾ › Other depth… (depth_typed.py)
            self._depth_typed.start()
        elif name == "sound_here":
            self._cuepick.start()
        elif name in ("lipsync", "blinks"):                              # the character sheets (rig_lipsync.py, rig_blinks.py)
            (self._lipsync if name == "lipsync" else self._blinks).start()
        elif name == "paint_fill":                                       # the fill picker's Paint it (painter.py)
            self.painter.paintFill()
        elif name == "copy_style":
            self._copied = self.selected_layers()[0]
            self._set_status(f"Copied the style of {self.label_of(self.doc.item(self._copied))}")
        else:
            raise ValueError(f'action {entry["id"]}: Rostrum2D has no "{name}" action')

    # ---- the doors QML and scripts call -------------------------------------------------------------------------
    def _commands(self):
        """Ctrl+K: the actions first (the same list as the bar and the menus), then the kit's commands they don't
        repeat."""
        out = [c for c in super()._commands() if not _covered(c["key"])
               and not (c.get("select") and self.doc.item(c["select"])["type"] in UNLISTED)]
        f = self._facts()
        if f.facts.get("any_locked"):               # a locked pick: only Unlock-like commands; the rest would refuse
            out = [c for c in out if not _needs_unlock(c)]
        mine = [{**({**c, "do": lambda k=c["key"]: self._hub.run(k)} if "do" in c else c), "own": True}
                for c in do_commands(LIST.available(f), self._what(f)) if not c["key"].startswith(TWINS)
                and (c.get("do") or not c.get("calls") or commands.runs(self.doc, c["calls"]))]
        taken = {LIST.job_of(a) for a in LIST.actions} | set(HAVE_ROWS) | {"select_all"}    # select_all: the row just below
        jobs = job_rows.rows(KEYS2D, set(ROUTES) | set(WINDOW) | set(SHELL) | {"play"}, taken,
                             state={"selected": bool(self.selected_layers()) and not self._keys.count and not self._stretch.shown,
                                    "problems": bool(self._problems.rows)})
        jobs = job_when.rows(self, jobs)
        return mine + [{"key": "layer:selectall", "label": "Select all layers", "hint": "Layer", "keys": "Ctrl+A",
                        "do": self.selectAllLayers, "own": True}] + jobs + out

    @Slot(str, result="QVariantList")
    def commands(self, query):
        found = [{k: c.get(k, "") for k in ("key", "label", "hint", "keys")} for c in commands.search(self._commands_now(), query)]
        return found

    def _commands_now(self):
        """Ctrl+K's list, worked out once per state: what may run is planned per entry (commands.runs, ~60-90 ms for
        a layer's ~160), and every keystroke in the box only filters it. An empty query (the box opening) works it out
        again; so does any change, pick, playhead or tool since."""
        state = (len(self.doc.history.changes), tuple(self._kit.selection), self._keys.count, self.time, self.tool,
                 self.painter.drawingId)
        if getattr(self, "_cmd_cache", (None,))[0] != state:
            self._cmd_cache = (state, self._commands())
        return self._cmd_cache[1]

    @Slot(str, result=bool)
    def run(self, key):
        """Ctrl+K, a menu or a script: an action of the list through the hub (one change), else the kit's."""
        if key.startswith("job:"):                      # a key-map job named in Ctrl+K (job_rows.py)
            self._hub.ask(key[4:])
            return True
        if not LIST.owns(key):
            return super().run(key)
        if key == "layer:delete" and self._stretch.shown:   # the short menu's Delete on a picked stretch (keys: KeyHub)
            return self.layerCommand("delete")
        entry = next((e for e in LIST.available(self._facts()) if e["id"] == key), None)
        self._hub.run(key)                          # not valid now: the hub says why in the status
        return entry is not None

    @Slot(str)
    def rowAction(self, key):
        """A settings row's own action (the Fill picker's + New painting: layer:painted_new), as from Ctrl+K."""
        self.run(key)

    @Slot(str, result=bool)
    def layerCommand(self, how):
        """A key's or a script's action by job (front, delete, group …): runs if valid now, else says why. While the
        pick is about keys, the jobs that act on keys run on them (key_edits.key_jobs)."""
        if self.keys_take("delete" if how == "layer:delete" else how):
            return True
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
        """Right-click: the frame's block first (Frame the view, Cut here …: frame_actions.menu_rows), then the short menu."""
        return frame_actions.menu_rows(LIST.available(self._facts())) + self._hub.menu()

    @Slot(str, result="QVariantList")
    def layerMenu(self, layer_id):
        """A layer's right-click (its row, or the canvas under the pointer): an unselected layer is selected alone
        first, a selected one keeps the selection; empty canvas ("" = no layer there) clears it (Paste, Select all);
        then the menu for the selection."""
        if layer_id and layer_id not in self.selected_layers():
            self.select(layer_id)
        elif not layer_id and self.selected_layers():       # empty canvas: nothing under the pointer, so nothing is picked
            self.clearSelection()
        entries = self.actionMenu()
        if not self.selected_layers() and any(c["type"] != "camera" for c in self.comp()["layers"]):   # empty canvas: Paste (if any) and Select all
            entries = entries + [{"value": "layer:selectall", "label": "Select all", "keys": "Ctrl+A", "group": "edit", "sub": []}]
        return entries

    @Slot("QVariantMap", result=str)
    def stepBack(self, state):
        """Esc: the one step the kit's ladder takes now (selection_rules.esc_step). "cancel" and "close" are the
        screen's own (it closes its panel or menu); "clear" clears the selection here."""
        editing = self._pen.editing                 # a path's points: Esc goes back to its box, the path stays picked
        step = esc_step({**state, "inner": bool(self._keys.count or self._stretch.shown or editing), "selected": bool(self.selected_layers())})
        if step == "clear_inner":                   # keys picked in the timeline go first, the layer stays picked
            layer = self.selected_layers()
            self._keys.clear()
            self._stretch.clear()                   # a picked stretch goes back to its layer the same way
            self._pen.editPoints(False)
            self.selectMany(layer)
        elif step == "clear":
            self.clearSelection()
        return step or ""
