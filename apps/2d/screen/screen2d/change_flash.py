"""Where the 1-second change outline goes on the canvas (Stage.qml's ChangeOutline over `backend.changeFlash.boxes`).

The kit's `agent.flash` names the items an agent's change, or the person's own undo / redo, just touched (agent_watch.py,
INTERACTION.md 1.21 rule 9). The outline is drawn round the picture ON SCREEN (shown.py), and that picture comes from the
engine a little after the change: an outline placed at once sat on the old place until the new picture landed. So the
boxes here are given only once the picture on screen shows the change, and then where it shows them: the outline comes
with the picture that shows the thing where it now is, never before. Nothing changes while the picture is unchanged, so
an outline's fade is never started again by a frame that changes nothing.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal


class ChangeFlash(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self._b, self._boxes = bridge, []
        bridge.agent.changed.connect(self._again)
        bridge.shownChanged.connect(self._again)

    def now(self) -> list[dict]:
        """One box per flashed item that shows ({id, x, y, w, h, rot, ax, ay}, composition px); none while the picture
        on screen is older than the document (the outline waits for the picture that shows the change)."""
        b = self._b
        if not b.agent.flash or not b.shows_now():
            return []
        return [dict(r, id=i) for i in b.agent.flash if (r := b.rectOf(i)).get("w") is not None]

    def _again(self, *_):
        got = self.now()
        if got != self._boxes:
            self._boxes = got
            self.changed.emit()

    boxes = Property("QVariantList", lambda self: self._boxes, notify=changed)
