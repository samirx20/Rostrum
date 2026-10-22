"""The soundtrack's render, off the screen's thread, newest request wins (screen2d/soundtrack.py asks).

One worker owns one RostrumSound engine process (rostrum_sound.engine.Engine: started on the first render, ended
by its own handle in close()). Each request reads the song whole, has the engine render its mix (rostrum_sound.
soundtrack.render: cached by content), reads the waveform's peaks once and the tempo grid, and answers `rendered`
with all of it. Any failure (no engine, a broken song, a missing marker) answers `failed` with the plain reason:
never silence passed off as the song.
"""
from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, Signal

from . import waveform


def open_engine():
    """The engine the soundtrack renders with (swap here, nowhere else)."""
    from rostrum_sound.engine import Engine
    return Engine()


class SoundtrackRender(QObject):
    rendered = Signal("QVariantMap")    # {item, name, file, seconds, peak, rate, peaks, grid, lines (voice_words.py)}
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cv = threading.Condition()
        self._pending, self._busy, self._stop = None, False, False
        self._thread = threading.Thread(target=self._run, name="render-soundtrack", daemon=True)
        self._thread.start()

    def request(self, folder: str, song: dict, end: float):
        with self._cv:
            self._pending = (folder, song, end)
            self._cv.notify()

    def busy(self) -> bool:
        with self._cv:
            return self._pending is not None or self._busy

    def _run(self):
        eng = None
        try:
            while True:
                with self._cv:
                    while self._pending is None and not self._stop:
                        self._cv.wait()
                    if self._stop:
                        return
                    (folder, song, end), self._pending, self._busy = self._pending, None, True
                try:
                    from rostrum_sound import soundtrack
                    root = soundtrack.read(folder, song["id"])
                    eng = eng or open_engine()
                    wav = soundtrack.render(eng, folder, root)
                    wave = waveform.peaks(wav)
                    grid = soundtrack.grid(root, max(end, wave["seconds"]))
                    from rostrum2d import voice_words
                    self.rendered.emit({"item": song["id"], "name": song["name"], "file": str(wav), **wave,
                                        "grid": grid, "lines": voice_words.lines(folder, root)})
                except Exception as e:  # noqa: BLE001  any failure is said, loudly
                    line = e.line() if hasattr(e, "line") else f"Error: soundtrack: {type(e).__name__}: {e}"
                    print(line, file=sys.stderr)
                    self.failed.emit(line)
                finally:
                    with self._cv:
                        self._busy = False
        finally:
            if eng is not None:
                eng.close()

    def close(self):
        with self._cv:
            self._stop = True
            self._cv.notify()
        self._thread.join(timeout=30)
