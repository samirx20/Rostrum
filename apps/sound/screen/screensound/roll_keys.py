"""Alt pressed or let go with the pointer still (CANVAS.md §4): the roll's pointer and its red "a click removes this" light
follow at once, not at the next move. A MouseArea hears the modifiers only with a pointer event, and the roll never
holds the keys, so this watches the window (the kit's GuiFilter: the keys reach a window first) and says only Alt's
changes. It never eats a key.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QGuiApplication
from rostrum_gui.gui_filter import GuiFilter

KEYS = (QEvent.Type.KeyPress, QEvent.Type.KeyRelease)


class AltWatch(GuiFilter):
    changed = Signal(bool)          # Alt is held now

    def __init__(self, parent=None):
        super().__init__(parent)
        self._held = False
        app = QGuiApplication.instance()
        if app is not None:
            self.watch_windows(app)

    def on_event(self, obj, event) -> bool:
        kind = event.type()
        if kind in KEYS and event.key() == Qt.Key.Key_Alt and not event.isAutoRepeat():
            self._say(kind == QEvent.Type.KeyPress)
        elif kind == QEvent.Type.WindowDeactivate:         # Alt+Tab away: its release goes to another window
            self._say(False)
        return False

    def _say(self, held: bool):
        if held != self._held:
            self._held = held
            self.changed.emit(held)
