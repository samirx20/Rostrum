"""The velocity strip under the Editor's roll (a slot mix-in for SoundBridge; velocity.py has the rules): one drag
is one gesture on the notes (or drum hits) of the track in the Editor, `endVelocity` ends it as one undo step.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_gui.edits import Drag

from . import velocity


class VelocitySlots:
    velocityFoldedChanged = Signal()

    def _vel_kept(self) -> dict:
        """The strip as the person left it with this song ({"h", "folded"}: view_kept.py `tools`), read once."""
        k = self.__dict__.get("_vel_state")
        if k is None:
            from . import view_kept
            got = (view_kept.read(self.doc.folder, self.doc.item_id).get("tools") or {}).get("velocity")
            got = got if isinstance(got, dict) else {}
            h = got.get("h")
            k = self.__dict__["_vel_state"] = {"folded": got.get("folded") is True,
                                               "h": velocity.strip_height(h) if isinstance(h, (int, float)) else velocity.STRIP_H}
        return k

    def _vel_keep(self):
        self._kept_view().keep_tools({"velocity": dict(self._vel_kept())})

    @Property(bool, notify=velocityFoldedChanged)
    def velocityFolded(self):
        """The strip is folded to its one thin row: the person's own screen state, never the song, never undone
        (kept with the song's view, so it comes back on reopen)."""
        return self._vel_kept()["folded"]

    @Slot()
    def toggleVelocityFold(self):
        self._vel_kept()["folded"] = not self.velocityFolded
        self._vel_keep()
        self.velocityFoldedChanged.emit()

    @Property(float, notify=velocityFoldedChanged)
    def velocityHeight(self):
        """The open strip's height (px) as dragged by its top edge: 52 … 240, kept like the fold."""
        return self._vel_kept()["h"]

    @Slot(float)
    def setVelocityHeight(self, h):
        h = velocity.strip_height(h)
        if h != self._vel_kept()["h"]:
            self._vel_kept()["h"] = h
            self._vel_keep()
            self.velocityFoldedChanged.emit()

    @Slot(str, result=bool)
    def beginVelocity(self, item_id):
        """Press on a bar (`item_id`) or on empty strip space ("": a line). A bar that is selected takes every
        selected note with it; an unselected one goes alone. True when there is something to change."""
        self.endDrag()
        roll = self._view["roll"]
        kind = "hit" if roll.get("kind") == "drums" else "note"
        blocks = roll.get("blocks", [])
        ids = self.selectedIds if item_id == "" or item_id in self.selectedIds else [item_id]
        grabs = velocity.grab(blocks, ids, kind)
        if not grabs:
            return False

        def go():
            self._grab = {"velocity": grabs, "primary": item_id}
            self._drag = Drag(self.doc, self.who, "Change velocity")
        return self._guard(go)

    @Slot(float, bool)
    def velocityBar(self, v, alt):
        """The pressed bar dragged to height `v` (0 … 1)."""
        g = self._grab
        if self._drag is not None and g and "velocity" in g:
            self._guard(lambda: self._drag.preview(velocity.bar_calls(g["velocity"], g["primary"], v, alt)))

    @Slot(float, float, float, float)
    @Slot(float, float, float, float, float)
    def velocityLine(self, t0, v0, t1, v1, reach=0.0):
        """A line drawn across the strip, from (t0 seconds, v0) to (t1, v1); `reach`: seconds past each end that still
        count (the screen's few px, velocity.line_calls)."""
        g = self._grab
        if self._drag is not None and g and "velocity" in g:
            self._guard(lambda: self._drag.preview(velocity.line_calls(g["velocity"], t0, v0, t1, v1, reach)))

    @Slot()
    def endVelocity(self):
        self.endDrag()
