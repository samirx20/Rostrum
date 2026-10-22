"""The Space key, as QML sees it (`spaceKey`): a tap plays or pauses; held, a drag on the canvas pans the view
(INTERACTION 1.12). A QML Shortcut only sees the press, so this watches press and release for the whole app.

`held`: Space is down now. `tapped`: Space went up and nothing used it (Stage.qml calls use() when a pan starts).
While a text field has the focus Space is left alone (it types a space). Key repeats are swallowed, so a held Space
never clicks a focused button either.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Property, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication


def _typing() -> bool:
    f = QGuiApplication.focusObject()
    return f is not None and (f.inherits("QQuickTextInput") or f.inherits("QQuickTextEdit"))


class SpaceKey(QObject):
    changed = Signal()
    tapped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._held, self._used = False, False
        QGuiApplication.instance().installEventFilter(self)

    @Property(bool, notify=changed)
    def held(self):
        return self._held

    @Slot()
    def use(self):
        """A pan used this press: letting go won't play."""
        self._used = True

    def eventFilter(self, obj, ev):  # noqa: N802 (Qt's name)
        kind = ev.type()
        if kind not in (QEvent.KeyPress, QEvent.KeyRelease, QEvent.ShortcutOverride) or ev.key() != Qt.Key_Space:
            return False
        if ev.modifiers() & ~Qt.KeypadModifier or (_typing() and not self._held):
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
