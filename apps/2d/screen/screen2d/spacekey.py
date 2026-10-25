"""The Space key, as QML sees it (`spaceKey`): a tap plays or pauses; held, a drag on the canvas pans the view
(INTERACTION 1.12). A QML Shortcut only sees the press, so this watches press and release on the window (Session.show; the kit's
gui_filter.py).

`held`: Space is down now. `tapped`: Space went up and nothing used it (Stage.qml calls use() when a pan starts).
While a text field has the focus Space is left alone (it types a space). Key repeats are swallowed, so a held Space
never clicks a focused button either.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Property, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication
from rostrum_gui.gui_filter import GuiFilter


def _typing(obj=None) -> bool:
    """A text field has the keyboard. `focusObject` is empty while the window is not the active one (a test window kept behind
    the person's work, a scripted run), so the window's own focus item is asked then: its caret is there all the same."""
    f = QGuiApplication.focusObject() or (obj.activeFocusItem() if hasattr(obj, "activeFocusItem") else None)
    return f is not None and (f.inherits("QQuickTextInput") or f.inherits("QQuickTextEdit"))


class SpaceKey(GuiFilter):
    changed = Signal()
    tapped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._held, self._used = False, False

    @Property(bool, notify=changed)
    def held(self):
        return self._held

    @Slot()
    def use(self):
        """A pan used this press: letting go won't play."""
        self._used = True

    def on_event(self, obj, ev):
        kind = ev.type()
        if kind not in (QEvent.KeyPress, QEvent.KeyRelease, QEvent.ShortcutOverride) or ev.key() != Qt.Key_Space:
            return False
        if ev.modifiers() & ~Qt.KeypadModifier or (_typing(obj) and not self._held):
            return False
        if kind == QEvent.KeyPress and not ev.isAutoRepeat() and not self._held:
            self._held, self._used = True, False
            self.changed.emit()
        elif kind == QEvent.KeyRelease and not ev.isAutoRepeat() and self._held:
            self._held = False
            self.changed.emit()
            if not self._used:
                self.tapped.emit()
        return kind != QEvent.ShortcutOverride
