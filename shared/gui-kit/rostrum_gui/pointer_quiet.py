"""Is the person pointing (or pressing keys) right now? A button is down, or a press, a release, a move, a wheel or a
key came in the last QUIET_S. Work that comes on its own (a finished render's meters and loudness, a settings panel made after a press,
the live link's tick) asks `busy()` and waits while it is true, so it never lands in the same screen refresh as a
click or a drag (sound-r5 M4: such work landing inside a click made it 35-70 ms).

One watcher for the whole app, made on the first `busy()` (gui_filter keeps it off Qt's own threads); per event it
only reads the clock. Without a Qt app (a script) nobody points: never busy.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication

from .gui_filter import GuiFilter

QUIET_S = 0.08          # five screen refreshes: a click's press and release, and the frame each one draws
POINTER = {QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick,
           QEvent.Type.MouseMove, QEvent.Type.Wheel,
           QEvent.Type.KeyPress, QEvent.Type.KeyRelease}    # a key is the person acting too (Ctrl+G's pick: its panel after)


class _Watch(GuiFilter):
    def __init__(self, app):
        super().__init__(app)
        self.last = 0.0
        self.watch_windows(app)         # the windows, never the whole app (gui_filter.watch_windows)

    def on_event(self, obj, event):
        if event.type() in POINTER:
            self.last = time.monotonic()
            if _before and event.type() in FIRST:
                for fn in _before[:]:
                    _before.remove(fn)
                    fn()
        return False


_watch: dict = {}           # the app -> its watcher (a test makes one app, a window run one)
FIRST = {QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.KeyPress}
_before: list = []          # run once before the next press or key (before_next_input)


def before_next_input(fn) -> None:
    """Run `fn` once before the next press or key reaches a window: work a click put off to the frame after (a made
    layer's pick, select_soon.py) is done before the person's next action reads it (Ctrl+D right after drawing)."""
    busy()                                  # (the watcher exists)
    if fn not in _before:
        _before.append(fn)


def busy() -> bool:
    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication):
        return False
    w = _watch.get(id(app))
    if w is None:
        w = _watch[id(app)] = _Watch(app)
    w.watch_windows(app)              # (a window made since)
    return QGuiApplication.mouseButtons() != Qt.MouseButton.NoButton or time.monotonic() - w.last < QUIET_S
