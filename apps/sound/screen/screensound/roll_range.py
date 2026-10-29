"""The keys a track's recorded sound has samples for, for the Editor's roll. The range is the engine's own
(note_ranges: `range`, asked once per sound and kept); this asks it on its own thread with its own engine, so a track's
first show never waits for the engine, and the roll shades the rows outside it (`rollPlayable`) when the answer comes.
The shade is only a hint of where the recorded samples end: a note outside it can be drawn, moved or pasted like any
other, and plays from the nearest sample, stretched to the written pitch. Synths and models play any key: no range,
nothing shaded.
"""
from __future__ import annotations

import json
import threading

from PySide6.QtCore import QObject, Signal
from rostrum_sound import note_ranges

from . import playback


class Asker(QObject):
    """Asks the engine for sounds' ranges, one at a time on a worker thread; `answered` on the window's thread."""
    answered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock, self._queue, self._asked, self._running = threading.Lock(), [], set(), False

    def want(self, inst: dict):
        key = json.dumps(inst, sort_keys=True)
        with self._lock:
            if key in self._asked:                 # asked already (a failed ask is not asked again this run)
                return
            self._asked.add(key)
            self._queue.append(inst)
            if self._running:
                return
            self._running = True
        threading.Thread(target=self._run, name="sound-ranges", daemon=True).start()

    def _run(self):
        eng = None
        try:
            while True:
                with self._lock:
                    if not self._queue:
                        self._running = False
                        return
                    inst = self._queue.pop(0)
                try:
                    eng = eng or playback.open_engine()
                    note_ranges.ask(eng, inst)
                except Exception:                  # no answer: the roll shades nothing (the render still says it)
                    continue
                self.answered.emit()
        finally:
            if eng is not None:
                try:
                    eng.close()
                except Exception:
                    pass


