"""D held moves the gizmo's pivot (SPEC 14), the key watcher for gizmo_qt.py."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication
from rostrum_gui.gui_filter import GuiFilter


class HoldD(GuiFilter):
    """D held moves the pivot (SPEC §14): Qt's shortcuts see only the key going down, so this watches for D going down
    and up (never while typing in a field, never auto-repeats). On the app: the gizmo has no window of its own; the kit's
    GuiFilter keeps it off Qt's own threads."""

    def __init__(self, gizmo):
        super().__init__(gizmo)
        self.gizmo = gizmo
        self.watch(QGuiApplication.instance())

    def on_event(self, obj, ev):
        mods = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        if ev.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease) and ev.key() == Qt.Key.Key_D                 and not ev.isAutoRepeat() and not ev.modifiers() & mods:
            focus = QGuiApplication.focusObject()
            typing = focus is not None and "Text" in focus.metaObject().className()
            if not (typing and ev.type() == QEvent.Type.KeyPress):
                self.gizmo.setPivot(ev.type() == QEvent.Type.KeyPress)
        return False
