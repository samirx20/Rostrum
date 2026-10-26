"""Rostrum2D's keys that are not actions on the selection: the one hub (`KeyHub`, the kit's ActionHub) answers every job of the
key map. An action of the list (actions.py) runs through the kit; a job in ROUTES calls a bridge method (below); a job in
WINDOW is the window's own (Main.qml `windowJobs`: it needs the canvas, the rail or the painter); the rest (keys2d.SKIP) are
bound by the kit's AppShell, FilesMenu and the few Shortcuts that need screen state. tests/test_keys_wired.py keeps the lists honest.
While the pick is about keys (key_select.about), every door (a key, a button, a menu, Ctrl+K) first offers its job to the
picked keys (key_edits.key_jobs: copy, cut, duplicate, delete, the arrows); a job they don't take runs as usual."""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_gui import pointer_quiet
from rostrum_gui.action_hub import ActionHub
from rostrum_gui.parts import SlotMixin

from . import levels
from .keys2d import ASKED, ROUTES, SKIP, WINDOW


class KeyHub(ActionHub):
    windowJob = Signal(str)             # a job only the window can run: Main.qml answers it

    def __init__(self, bridge, *a, **kw):
        super().__init__(*a, parent=bridge, **kw)
        self.bridge = bridge

    @Property("QVariantList", constant=True)
    def skip(self):
        return SKIP

    @Slot(str)
    def key(self, job):
        pointer_quiet.acted()           # the person acting (a shortcut's key never reaches the window's watcher)
        if self.bridge.keys_take(job):
            return
        if job in ROUTES:
            name, *args = ROUTES[job]
            getattr(self.bridge, name)(*args)
        elif job in WINDOW:
            self.windowJob.emit(job)
        else:
            super().key(job)

    @Slot(str)
    def run(self, id_):
        if not self._keys_took(id_):
            super().run(id_)

    @Slot(str)
    def choose(self, id_):
        if not self._keys_took(id_):
            super().choose(id_)

    def _keys_took(self, id_) -> bool:
        a = self.list.find(id_)
        return a is not None and self.bridge.keys_take(self.list.job_of(a))

    def ask(self, job):
        """Ctrl+K named a job of the key map (not an action): a route, else the window's (Main.qml, then the kit's AppShell.runJob)."""
        if self.bridge.keys_take(job):
            return
        if job in ROUTES or job in ASKED:
            name, *args = (ROUTES | ASKED)[job]
            getattr(self.bridge, name)(*args)
        else:
            self.windowJob.emit(job)


class KeyRoutes(SlotMixin):
    """The bridge methods keys2d.ROUTES names."""

    @Slot(int)
    def stepFrames(self, n):
        """Ctrl+Left / Right (one frame), with Shift (ten)."""
        self.setTime(self._t + n / self.comp()["fps"])

    @Slot()
    def toEnd(self):
        self.setTime(self.comp()["duration"])

    @Slot()
    def markerHere(self):
        """M: a marker at the playhead."""
        if self.marks.add(self._t):
            self._set_status(f"Marker added at {self._t:.2f} s")

    @Slot(int)
    def markerJump(self, sign):
        """Alt+M / Alt+Shift+M: the playhead to the next / previous marker (a clear word when there is none)."""
        half = 0.5 / self.comp()["fps"]
        times = sorted(m["at"] for m in self.marks.rows())
        to = [t for t in times if t > self._t + half] if sign > 0 else [t for t in times if t < self._t - half]
        if not to:
            return self._set_status("No next marker" if sign > 0 else "No earlier marker")
        self.setTime(to[0] if sign > 0 else to[-1])

    @Slot(str)
    def nudgeKey(self, how):
        """An arrow key (NUDGE: "left", "right_big" ...): moves the picked layers, with the Select tool only (picked
        keys take the arrows first: KeyHub.key)."""
        if self._tool == "move":
            name, _, size = how.partition("_")
            step = {"": 1, "big": 10, "fine": 0.1}[size]
            self.nudge(*{"left": (-step, 0), "right": (step, 0), "up": (0, -step), "down": (0, step)}[name])

    @Slot()
    def selectAllKey(self):
        """Ctrl+A: every layer; the pick is about layers then (picked keys go)."""
        if self._tool == "move":
            self._keys.clear()
            self.selectAllLayers()

    @Slot(str)
    def toolKey(self, tool):
        """A tool's key: the tool; P again goes back to Select; J says why when no rig is picked."""
        if tool == "bone" and not self._bone_tool.available:
            return self._set_status("Pick a rig to use the Bone tool")
        self.setTool("move" if tool == self._tool == "pen" else tool)

    # ---- Tab, Shift+Tab, Enter, Shift+Enter: the layers at this level (levels.py) ---------------------------------
    @Slot(int)
    def walk(self, sign):
        """Tab / Shift+Tab: the next / previous layer at this level (one pick), with the Select tool only."""
        if self._tool == "move":
            pick = levels.next_to(self.doc, self.selected_layers(), sign, self.comp_id)
            if pick:
                self.select(pick)

    @Slot(result=bool)
    def canGoIn(self):
        """Enter would go into the picked group (Main.qml: the Enter that text and path points don't take)."""
        one = self.selected_layers()
        return len(one) == 1 and bool(levels.first_child(self.doc, one[0]))

    @Slot()
    def goIn(self):
        """Enter on a group: its first layer."""
        one = self.selected_layers()
        if self._tool == "move" and len(one) == 1 and levels.first_child(self.doc, one[0]):
            self.select(levels.first_child(self.doc, one[0]))

    @Slot()
    def goOut(self):
        """Shift+Enter: the group the pick is in becomes the pick."""
        picked = self.selected_layers()
        if self._tool == "move" and picked and levels.parent_group(self.doc, picked[-1]):
            self.select(levels.parent_group(self.doc, picked[-1]))
