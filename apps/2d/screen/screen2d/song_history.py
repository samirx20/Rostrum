"""The song that plays, in 2D's one undo history (DocBridge.join_history, rostrum_core.desk): Add a sound here is one
change in RostrumSound's song (rostrum2d/sound_cues.py), so Ctrl+Z in 2D takes it back in one step, and Ctrl+Shift+Z
brings it back. The song is project_sound.open_song's live copy (one door with Sound's own window and the cue code).
Changes kept in step by 2D's sound link (sound_cues.LINK: markers, video sound) are not news: they are not announced.
The Soundtrack (soundtrack.py) owns one and calls `touch()` when the song's file changed.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from rostrum_core import RostrumError
from rostrum2d import project_sound, sound_cues


class SongHistory(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._last = bridge, None

    def history_doc(self):
        """The song that plays now, caught up (None: no project folder, no Sound item, or a song that can't be read:
        the Sound row says why, loudly; Undo goes on in the other documents)."""
        folder = self.b.doc.folder
        try:
            song = project_sound.song(folder, self.b.comp().get("soundtrack", "")) if folder else None
            return project_sound.open_song(folder, song["id"]) if song else None
        except RostrumError:
            return None

    def stepped(self, doc):
        """An undo or redo landed in the song (saved by its door): the Sound row renders it again at once."""
        self.parent().check()

    def touch(self):
        doc = self.history_doc()
        c = doc.history.changes[-1] if doc is not None and doc.history.changes else None
        self._last = c if c is not None and c.who != sound_cues.LINK else None
        self.changed.emit()

    def last_change(self):
        return self._last
