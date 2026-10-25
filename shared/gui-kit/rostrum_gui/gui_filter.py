"""The one base for a Python event filter (every app's key and pointer watchers use it).

Qt calls an event filter for every event its target gets, from whatever thread sends it. A filter on the whole app
also hears events Qt's own threads send to the app's objects (the image loader making a brush tip list or a gradient
swatch): Python then runs on a thread with no Python of its own, beside the GUI thread, and the app dies with an
access violation (A1b: the Tip list and a gradient's own length). So:

    watch(win)      install on a window (the keys and the pointer reach the window first), never on the whole app
    on_event(o, e)  the filter's own work; True eats the event

`eventFilter` runs `on_event` only on the GUI thread, and a Python error in it is reported through qt_faults (loud:
a scripted run fails, a person's run logs it) and the event goes on: one bad filter never takes the app down.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject

from . import qt_faults

GUI_THREAD = threading.main_thread().ident


class GuiFilter(QObject):
    def watch(self, target):
        """Watch `target`'s events (a window, or the app for a part that has no window: say why where it's used)."""
        target.installEventFilter(self)

    def watch_windows(self, app):
        """Watch every window of the app, those made later too (each is taken in when it gets the keys, or at the
        next call): the pointer and the keys reach a window first. A filter on the app itself runs Python for every
        event of every object (timers, queued calls, deletions: ~250 a Ctrl+G, 2-5 ms)."""
        seen = self.__dict__.setdefault("_windows", set())
        for w in [*app.topLevelWindows(), app.focusWindow()]:
            if w is not None and id(w) not in seen:
                seen.add(id(w))
                self.watch(w)
                w.destroyed.connect(lambda _=None, i=id(w): seen.discard(i))
        if not self.__dict__.get("_following"):
            self._following = True
            app.focusWindowChanged.connect(lambda _w: self.watch_windows(app))

    def on_event(self, obj, event) -> bool:
        return False

    def eventFilter(self, obj, event):          # noqa: N802 (Qt's name)
        if threading.get_ident() != GUI_THREAD:     # Qt's own threads: never run Python on them
            return False
        try:
            return bool(self.on_event(obj, event))
        except Exception:                           # noqa: BLE001 (reported loudly, the app carries on)
            qt_faults.python_error(f"{type(self).__name__}.on_event")
            return False
