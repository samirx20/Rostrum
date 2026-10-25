"""A check's window is laid out before every press, key and wheel turn it is given, so a scripted hand never clicks where a
control was a moment ago.

Qt lays out (polishes) a window's rows, columns and anchors only while drawing a frame. A window behind the person's
work draws on its own screen thread (app.py `background`), but Windows gives it no frame at all while the screen is
asleep or the window is fully covered on some drivers: a step that changed the layout (a row appearing, a panel
folding) then left every later position as it was, and the next click landed on the old place (the Gap row in 2D,
merging P-a). A window that drew no frame since the input before draws one now, itself (`grabWindow`: lays out,
draws, never shows or raises the window), before the press, key or wheel turn goes in. A window that is drawing anyway
costs nothing.

Only in windows opened behind the person's work (scripts, agents, tests): the person's own window draws every frame."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Slot

_SETTLE = {QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.KeyPress, QEvent.Type.Wheel}
# (a release goes to whatever took the press, wherever it is now)


class LaidOut(QObject):
    _win = None                                           # (class defaults: Python may drop the instance's first at exit)
    _grabbing = False

    def __init__(self, win):
        super().__init__(win)
        self._win, self._drew, self._grabbing = win, False, False
        self.grabs = 0                                    # how often the window had to be drawn here (for checks)
        win.frameSwapped.connect(self._swapped, Qt.ConnectionType.DirectConnection)
        win.installEventFilter(self)

    @Slot()
    def _swapped(self):
        self._drew = True

    def eventFilter(self, obj, event):
        if obj is self._win and event.type() in _SETTLE and not self._grabbing:
            if not self._drew:                            # nothing drawn since the last input: lay it out now
                self._grabbing = True
                try:
                    self._win.grabWindow()
                    self.grabs += 1
                finally:
                    self._grabbing = False
            self._drew = False                            # this input may change the layout: the next one checks again
        return False


def watch(win) -> LaidOut:
    """Keep `win` laid out for scripted input (kept on the window: one per window)."""
    got = win.findChild(LaidOut)
    return got if got is not None else LaidOut(win)
