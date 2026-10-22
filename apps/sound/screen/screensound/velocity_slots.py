"""The velocity strip under the Editor's roll (a slot mix-in for SoundBridge; velocity.py has the rules): one drag
is one gesture on the notes (or drum hits) of the track in the Editor, `endVelocity` ends it as one undo step.
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui.edits import Drag

from . import velocity


class VelocitySlots:
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
    def velocityLine(self, t0, v0, t1, v1):
        """A line drawn across the strip, from (t0 seconds, v0) to (t1, v1)."""
        g = self._grab
        if self._drag is not None and g and "velocity" in g:
            self._guard(lambda: self._drag.preview(velocity.line_calls(g["velocity"], t0, v0, t1, v1)))

    @Slot()
    def endVelocity(self):
        self.endDrag()
