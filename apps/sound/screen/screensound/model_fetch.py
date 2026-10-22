"""Asks before downloading a clean-up model, then downloads it on a worker thread (Sam: models ship with the app but
are fetched only when a clean-up first needs one). Exposed to QML as `mixer.cleaning.download`; ModelDownload.qml shows it.

    ask(models) -> state "asking" (question with size and licence; the person says start() or dismiss())
    start()     -> "downloading" (progress 0..1, cancel() stops it and removes the partial file)
    then "done" (`ready` is emitted: the clean-up carries on) or "failed" (error text, in words) or back to "idle".
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import RostrumError
from rostrum_sound.cleanup import fetch

NAMES = {"deepfilternet3": "DeepFilterNet 3 (noise removal)", "umxhq": "Open-Unmix UMX-HQ (stem separation)",
         "qwentts": "the voice (Qwen3-TTS)"}


def _groups(models) -> list[tuple]:
    """(id, total bytes, licences) per model folder: the voice is three files but one question."""
    out: dict = {}
    for m in models:
        size, lic = out.get(m.id, (0, []))
        out[m.id] = (size + m.size, lic + [x for x in [licence_line(m)] if x not in lic])
    return [(i, size, " and ".join(lic)) for i, (size, lic) in out.items()]


def licence_line(m) -> str:
    return m.licence.split("(")[0].strip()          # "MIT OR Apache-2.0"


class ModelFetch(QObject):
    changed = Signal()
    ready = Signal()                                # every asked-for model is installed
    cancelled = Signal()
    _tick = Signal(int, int)
    _end = Signal(str)                              # from the worker: "" = installed, else the error line

    def __init__(self, parent=None):
        super().__init__(parent)
        self._needs: list = []
        self._state, self._progress, self._error, self._note = "idle", 0.0, "", ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._tick.connect(self._on_tick)
        self._end.connect(self._on_end)

    @Property(str, notify=changed)
    def state(self):
        return self._state

    @Property(str, notify=changed)
    def question(self):
        parts = [f"{NAMES.get(i, i)} ({size / 1e6:.0f} MB, {lic})" for i, size, lic in _groups(self._needs)]
        what = "Speaking a line" if any(m.id == "qwentts" for m in self._needs) else "This clean-up"
        return f"{what} needs {' and '.join(parts)}. Download {'it' if len(parts) == 1 else 'them'} now?"

    @Property(float, notify=changed)
    def progress(self):
        return self._progress

    @Property(str, notify=changed)
    def note(self):
        return self._note

    @Property(str, notify=changed)
    def error(self):
        return self._error

    def ask(self, models) -> None:
        self._needs, self._error, self._progress, self._note = list(models), "", 0.0, ""
        self._state = "asking"
        self.changed.emit()

    @Slot()
    def start(self):
        if self._state not in ("asking", "failed") or not self._needs:
            return
        self._state, self._error, self._progress, self._stop = "downloading", "", 0.0, threading.Event()
        self.changed.emit()
        self._thread = threading.Thread(target=self._work, args=(list(self._needs), self._stop), daemon=True)
        self._thread.start()

    @Slot()
    def cancel(self):
        """Stops a download (the partial file goes) or closes the question."""
        if self._state == "downloading":
            self._stop.set()
        else:
            self._state = "idle"
            self.changed.emit()

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _work(self, models, stop):
        try:
            for i, m in enumerate(models):
                self._note = f"{NAMES.get(m.id, m.id)}" + (f" ({i + 1} of {len(models)}: {m.file})" if len(models) > 1 else "")
                fetch.install(m, progress=lambda done, total: self._tick.emit(done, total), cancel=stop)
            err = ""
        except RostrumError as e:
            err = "cancelled" if stop.is_set() else e.line()
        except Exception as e:  # noqa: BLE001  shown on the screen, whatever it was
            err = f"Error: download: {e}"
        self._end.emit(err)

    def _on_tick(self, done, total):
        self._progress = done / max(total, 1)
        self.changed.emit()

    def _on_end(self, error):
        if error == "cancelled":
            self._state = "idle"
            self.changed.emit()
            self.cancelled.emit()
        elif error:
            self._state, self._error = "failed", error
            self.changed.emit()
        else:
            self._state, self._progress = "done", 1.0
            self.changed.emit()
            self.ready.emit()
