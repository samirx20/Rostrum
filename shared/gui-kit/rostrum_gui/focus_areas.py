"""Which area of the window the person last pressed in (INTERACTION.md 1.20): the area that takes the keys
(AppShell.pressedAt; a press shows no mark, only F6 lights the area's top edge). Watched here, before any item sees the press, because a press that a
canvas or list takes for itself never reaches a handler on the shell. `start` installs it on every AppShell window."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QMetaObject, Q_ARG

from .gui_filter import GuiFilter

PRESSES = (QEvent.Type.MouseButtonPress, QEvent.Type.TabletPress, QEvent.Type.TouchBegin)


class FocusAreas(GuiFilter):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.watch(win)

    def on_event(self, obj, event):
        if obj is self.win and event.type() in PRESSES:
            p = event.points()[0].position() if hasattr(event, "points") and event.points() else event.position()
            QMetaObject.invokeMethod(self.win, "pressedAt", Q_ARG("QVariant", p.x()), Q_ARG("QVariant", p.y()))
        return False


def watch(win):
    """Install the watcher on an AppShell window (one with pressedAt); other windows are left alone."""
    if win.metaObject().indexOfMethod("pressedAt(QVariant,QVariant)") >= 0:
        return FocusAreas(win)
    return None
