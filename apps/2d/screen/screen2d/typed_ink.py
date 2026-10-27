"""Typed words show under the caret at once (backend.create.ink): while the picture on screen is older than what was
typed, the typing box (CreateOverlay.qml) draws the words itself, in the text's own font (the face Qt draws the engine's
family in: project_picks.face_of), size, colour and turn; when the engine's picture of them lands, the box's words go
clear again and the picture shows them. Same font, same place: the hand-over can't be seen. The document and the
picture never wait for this; it only fills the frames between a key and the engine's picture of it.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal

from . import project_picks


class TypedInk(QObject):
    changed = Signal()

    def __init__(self, bridge, create):
        super().__init__(create)
        self.b, self.create, self._ahead, self._face = bridge, create, False, ""
        bridge.shownChanged.connect(self._check)        # a picture landed
        create.typingChanged.connect(self._check)       # a key (typing_session.py), or typing began / ended

    def _check(self):
        typing = self.create.typing
        ahead = typing and bool(self.create.body) and not self.b.shows_now()
        face = project_picks.face_of(self.create.style.get("font", "")) if typing else ""
        if (ahead, face) != (self._ahead, self._face):
            self._ahead, self._face = ahead, face
            self.changed.emit()

    @Property(bool, notify=changed)
    def ahead(self):
        """The typed words are newer than the picture on screen: the typing box draws them."""
        return self._ahead

    @Property(str, notify=changed)
    def face(self):
        """The Qt family that draws the text's font ("" = not known yet: the box keeps the screen's font)."""
        return self._face
