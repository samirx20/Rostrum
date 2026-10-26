"""A window's link to the agents working on the same project (INTERACTION.md 1.18):
- the agent's steps arrive live: every TICK_MS the window takes in what an agent's server saved (rostrum_core.live),
  as ordinary change events, so the bridge, History and the agent chip see them and nothing on screen moves;
- the agent sees what the person sees: the app's `state_fn(bridge)` (selection, playhead, range, scene, focus, view,
  dragging) is written for `inspect_screen` whenever it differs (rostrum_core.screen_state), on the link's own thread
  (`settle()` waits for it). Screen state, not a change;
- the whole document file is written here, between pointer actions, once the person pauses (live.Live.fold_if_quiet),
  never inside a click or a drag, its text made a slice of ~3 ms at a time between events and written on a thread of
  its own (a key pressed meanwhile never waits; a failed write is said in the top bar): each change only appends its
  line to the history file.

    link = LiveLink(bridge, "2d", screen_seen.state)      # after live.keep(doc); link.close() when the window closes

A document outside a project folder has no link (nothing else can open it).
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer
from rostrum_core import RostrumError, screen_state

from . import pointer_quiet

TICK_MS = 300


class Later:
    """A part of the screen state made on the link's own thread, only when it is written: `key` says when it changed
    (compared with ==; hold what it names, so an id in it stays that object's), `make()` the value (it reads only
    what never changes in place: a song's items, its data). Naming 3,000 selected notes on the screen's thread cost
    ~40-70 ms each time the selection changed."""
    __slots__ = ("key", "make")

    def __init__(self, key, make):
        self.key, self.make = key, make

    def __eq__(self, other):
        return isinstance(other, Later) and other.key == self.key


def _write(folder, item, app, state):
    screen_state.write(folder, item, app, {k: v.make() if isinstance(v, Later) else v for k, v in state.items()})


class LiveLink(QObject):
    def __init__(self, bridge, app: str, state_fn, parent=None):
        super().__init__(parent or bridge)
        self.bridge, self.app, self.state_fn, self._said = bridge, app, state_fn, None
        self._writer = ThreadPoolExecutor(1, thread_name_prefix=f"screen-state-{app}")   # the file, off the screen's thread
        self._written = None                      # the last write's future: its failure is said at the next tick
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)
        if bridge.doc.live is not None:
            bridge.doc.live.windowed()            # the whole document file is written on this timer, not in a change
        if bridge.doc.folder is not None:
            self._timer.start(TICK_MS)

    def tick(self):
        if pointer_quiet.busy():                  # never inside a click or a drag: the next tick takes it in
            return
        doc = self.bridge.doc
        try:
            if doc.live is not None:
                doc.live.windowed()               # (the bridge may hold another document now)
                doc.live.catch_up()
                if doc.live.fold_if_quiet():
                    self._fold_work()             # its text a slice at a time, between events
            if self._written is not None and self._written.done():
                done, self._written = self._written, None
                done.result()                     # a failed write raises here, on the screen's thread
            state = self.state_fn(self.bridge)
            if state != self._said:               # written on the link's own thread (a file write on a pick: ~2-4 ms)
                self._written = self._writer.submit(_write, doc.folder, doc.item_id, self.app, state)
                self._said = state
        except (RostrumError, OSError) as e:      # loud, once per failure, and the window keeps working
            line = e.line() if isinstance(e, RostrumError) else f"Error: what the screen shows could not be written for agents: {e}"
            if line != getattr(self, "_failed", None):
                self._failed = line
                print(line, file=sys.stderr)
                fail = getattr(self.bridge, "_fail", None)
                if fail:
                    fail(line, e.person() if isinstance(e, RostrumError) else None)

    def _fold_work(self):
        live = self.bridge.doc.live
        if live is not None and live.fold_work():
            QTimer.singleShot(0, self._fold_work)

    def settle(self):
        """Wait for the last write of what the screen shows and of the document file (a script that reads them right
        after a tick)."""
        if self._written is not None:
            self._written.result()
        if self.bridge.doc.live is not None:
            self.bridge.doc.live.settle()

    def close(self):
        self._timer.stop()
        self._writer.shutdown(wait=True)          # the last write lands before the file is cleared
        self.bridge.doc.drop_gesture()            # an open drag or preview box is cancelled, never saved as if kept
        if self.bridge.doc.live is not None:
            self.bridge.doc.live.fold(always=False)   # the document file up to date: readers of the file alone see the end
        if self.bridge.doc.folder is not None:
            screen_state.clear(self.bridge.doc.folder, self.app)
