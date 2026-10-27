"""Esc during a drag puts everything back (INTERACTION.md 1.22 canvas rule 5), in ONE place for every app: while a
drag runs it holds the window's Esc, so Esc never reaches a popup, a field or the selection's "step back" first; it
cancels the drag (the document as before, no undo step) and the press's release then does nothing.

    ESC.hold(cancel)       # a drag started (PointerDrag does this itself once the press moves 4 px)
    ESC.let_go(cancel)     # it ended (release or cancel)
    QML: dragEsc.holdEsc() / dragEsc.letEsc(), and Connections { target: dragEsc; function onCancelled() { … } }

One application event filter, installed on the first hold. Holding again replaces the drag held (a new press can
only start after the last one ended). A cancel that raises is reported (qt_faults), never swallowed, and the hold is
let go either way, so Esc is never left eaten.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication


class EscCancels(QObject):
    cancelled = Signal()          # a drag QML holds (`hold()`) was cancelled by Esc: put it back, record nothing

    def __init__(self):
        super().__init__()
        self._cancel, self._installed = None, False

    @property
    def held(self) -> bool:
        return self._cancel is not None

    def hold(self, cancel) -> None:
        self._cancel = cancel
        app = QGuiApplication.instance()
        if not self._installed and app is not None:
            app.installEventFilter(self)
            self._installed = True

    def let_go(self, cancel=None) -> None:
        """The drag ended. `cancel`: only if it is still the one held (a late release of an older drag lets go nothing)."""
        if cancel is None or cancel == self._cancel:     # (== : a bound method is a new object each read)
            self._cancel = None

    @Slot()
    def hold_qml(self):
        """QML's door (the `dragEsc` context value): `dragEsc.holdEsc()` when a QML drag starts, `dragEsc.letEsc()` when
        it ends; Esc meanwhile sends `cancelled` (the drag puts itself back) and nothing else hears it."""
        self.hold(self.cancelled.emit)

    @Slot()
    def let_qml(self):
        self.let_go(self.cancelled.emit)

    holdEsc, letEsc = hold_qml, let_qml

    def press(self) -> bool:
        """Esc pressed: cancel the drag held (True), or nothing held (False). The event filter's work, callable alone."""
        cancel, self._cancel = self._cancel, None
        if cancel is None:
            return False
        try:
            cancel()
        except Exception:
            from . import qt_faults
            qt_faults.python_error("Esc during a drag", "Cancel the drag")
        return True

    def eventFilter(self, obj, event):
        if (self._cancel is not None and event.type() in (QEvent.KeyPress, QEvent.ShortcutOverride)
                and event.key() == Qt.Key_Escape):
            if event.type() == QEvent.ShortcutOverride:      # no window shortcut takes it first (KeyShortcut's Esc)
                event.accept()
                return True
            return self.press()
        return False


ESC = EscCancels()
