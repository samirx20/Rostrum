"""Sound's rule for Python's cycle collector after an edit (the kit's heap.py, made rarer and kept off playback).

The kit sets what an edit leaves aside once the person pauses (gc.freeze, no walk: kept here as it is), and 8 s after
each edit, at the next 3-s pause, walks everything alive once (unfreeze, collect, freeze: ~0.2 s on the Big song).
A key that lands in that walk waits for it (core r2: 640-840 M cycles inside a whole-song Ctrl+D or Ctrl+Z, on about
one key in five when keys come a few seconds apart). Here the full walk comes only when there is something to find:
once what has been set aside grew by GROW since the last walk (cycles left by edits are among it, so they are freed
then: memory grows by at most that share between walks), after a longer pause (IDLE_S), and never while the song plays
(a walk then would stall the playhead).
"""
from __future__ import annotations

import gc

from PySide6.QtCore import QTimer
from rostrum_gui import heap, pointer_quiet

PAUSE_MS = 700      # after an edit: set aside without a walk (as the kit)
REST_MS = 8000      # after an edit and no other: ask whether a walk is due
IDLE_S = 5.0        # the walk waits for this long a pause in the person's input
GROW = 0.15         # a walk once what is set aside grew by this share since the last one
RETRY_MS = 1000


class HeapRule:
    def __init__(self, parent, playing):
        """`playing()`: the song is playing (the walk waits until it stops)."""
        self._playing = playing
        self._walked = 0
        self._pause = QTimer(parent, singleShot=True, interval=PAUSE_MS, timeout=self._set_aside)
        self._rest = QTimer(parent, singleShot=True, interval=REST_MS, timeout=self._walk)

    def after_edit(self):
        """An edit just landed: set aside after a pause, a walk after a rest when one is due. A newer edit starts both
        waits again."""
        self._pause.start(PAUSE_MS)
        self._rest.start(REST_MS)

    def _set_aside(self):
        if pointer_quiet.busy():                # never beside a click or a key
            return self._pause.start(RETRY_MS // 2)
        gc.freeze()

    def _walk(self):
        if not self._walked:                    # the first edit since the song opened (the kit walked at the open)
            gc.freeze()
            self._walked = gc.get_freeze_count()
            return
        if gc.get_freeze_count() < self._walked * (1 + GROW):
            return gc.freeze()                  # nothing much new: set aside, no walk
        if self._playing() or not pointer_quiet.idle_for(IDLE_S):
            return self._rest.start(RETRY_MS)
        heap.calm_now()
        self._walked = gc.get_freeze_count()
