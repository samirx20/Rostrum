"""Hold keys (keymap.py `"hold": True`): Qt's shortcuts only see a key go down, so this watches the window for the key
coming up and calls hub.keyUp(job). A key held while the window loses focus is let go then too, so a held "hear the
original" never sticks on. Installed by the action hub only when the app's map has a hold key; auto-repeats are
ignored, and a press the shortcuts didn't run (typing in a field) has no release to run (the hub checks).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QGuiApplication, QKeySequence


class KeyHold(QObject):
    def __init__(self, hub, keymap):
        super().__init__(hub)
        self.hub, self.keymap = hub, keymap
        self.jobs = [e["job"] for e in keymap.entries() if e["hold"]]
        app = QGuiApplication.instance()
        if self.jobs and app is not None:
            app.installEventFilter(self)
            app.applicationStateChanged.connect(self._state)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyRelease and not event.isAutoRepeat():
            name = QKeySequence(event.key()).toString()
            if name:
                for job in self.keymap.held(name):
                    self.hub.keyUp(job)
        return False

    def _state(self, state):
        from PySide6.QtCore import Qt
        if state != Qt.ApplicationState.ApplicationActive:
            for job in self.jobs:
                self.hub.keyUp(job)
