"""A window's link to the agents working on the same project (INTERACTION.md 1.18):
- the agent's steps arrive live: every TICK_MS the window takes in what an agent's server saved (rostrum_core.live),
  as ordinary change events, so the bridge, History and the agent chip see them and nothing on screen moves;
- the agent sees what the person sees: the app's `state_fn(bridge)` (selection, playhead, range, scene, focus, view,
  dragging) is written for `inspect_screen` whenever it differs (rostrum_core.screen_state). Screen state, not a change.

    link = LiveLink(bridge, "2d", screen_seen.state)      # after live.keep(doc); link.close() when the window closes

A document outside a project folder has no link (nothing else can open it).
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QTimer
from rostrum_core import RostrumError, screen_state

from . import pointer_quiet

TICK_MS = 300


class LiveLink(QObject):
    def __init__(self, bridge, app: str, state_fn, parent=None):
        super().__init__(parent or bridge)
        self.bridge, self.app, self.state_fn, self._said = bridge, app, state_fn, None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)
        if bridge.doc.folder is not None:
            self._timer.start(TICK_MS)

    def tick(self):
        if pointer_quiet.busy():                  # never inside a click or a drag: the next tick takes it in
            return
        doc = self.bridge.doc
        try:
            if doc.live is not None:
                doc.live.catch_up()
            state = self.state_fn(self.bridge)
            if state != self._said:
                screen_state.write(doc.folder, doc.item_id, self.app, state)
                self._said = state
        except RostrumError as e:                 # loud, once per failure, and the window keeps working
            line = e.line()
            if line != getattr(self, "_failed", None):
                self._failed = line
                print(line, file=sys.stderr)
                fail = getattr(self.bridge, "_fail", None)
                if fail:
                    fail(line)

    def close(self):
        self._timer.stop()
        if self.bridge.doc.live is not None:
            self.bridge.doc.save()                # fold the history into the document file: readers of the file alone see the end
        if self.bridge.doc.folder is not None:
            screen_state.clear(self.bridge.doc.folder, self.app)
