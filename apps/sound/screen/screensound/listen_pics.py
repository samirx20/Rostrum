"""The listen pictures of the last render: the loudness curves and the spectrum, from `rostrum_sound.listen`'s numbers
drawn for the panel (listen_draw.py) off the GUI thread into a folder, refreshed when the render changes. A failure is shown on the panel, never hidden.

Each picture gets a new file name per render (`loudness-3.png`), so the QML Image never shows a stale cache.
"""
from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot


def series_pairs(series: dict) -> list[tuple[float, float | None]]:
    """The engine's short-term series [(time_s, lufs)]: value k is the window ending at k * hop + window."""
    hop, window = float(series.get("hop", 0.1)), float(series.get("shortTermWindow", 3.0))
    return [(round(k * hop + window, 3), v) for k, v in enumerate(series.get("shortTerm") or [])]


_DRAWING = threading.Lock()      # matplotlib's pyplot is not thread-safe: one drawing at a time


def make_pictures(render: dict, folder: Path, n: int) -> dict:
    """Both pictures of one render answer -> {"loudness": path, "spectrum": path}. Raises on any failure."""
    import numpy as np
    from rostrum_sound.listen.core import load
    from rostrum_sound.listen.loudness import short_term

    from .listen_draw import loudness_panel, spectrum_panel
    wav = render.get("file")
    if not wav or not Path(wav).is_file():
        raise FileNotFoundError(f"the render's file is not there: {wav}")
    folder.mkdir(parents=True, exist_ok=True)
    loud, spec = folder / f"loudness-{n}.png", folder / f"spectrum-{n}.png"
    y, sr = load(wav)
    if render.get("series"):
        pairs = series_pairs(render["series"])
        t, st = np.array([p[0] for p in pairs], float), np.array([-200.0 if p[1] is None else p[1] for p in pairs], float)
    else:
        t, st = short_term(y, sr)
    with _DRAWING:
        lufs = render.get("lufs")          # the integrated loudness the engine already measured: not measured again here
        loudness_panel(y, sr, t, st, loud, None if lufs is None else float(lufs))
        spectrum_panel(y, sr, spec)
    for old in folder.glob("*.png"):
        if old not in (loud, spec):
            try:
                old.unlink()
            except OSError:
                pass                              # still shown a moment longer; the next render clears it
    return {"loudness": str(loud), "spectrum": str(spec)}


class ListenPics(QObject):
    changed = Signal()
    _done = Signal(int, dict, str)           # version, paths, error (from the worker thread)

    def __init__(self, bridge, folder=None, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._own = folder is None                   # a folder we made is ours to delete on close
        self._folder = Path(folder or tempfile.mkdtemp(prefix="rostrum-sound-pics-"))
        self._threads: list[threading.Thread] = []
        self._closed = False
        self._paths: dict = {}
        self._status, self._version, self._busy = "", 0, False
        self._done.connect(self._finish)
        bridge.renderChanged.connect(self.refresh)
        if bridge.lastRender:
            self.refresh()

    @Property(str, notify=changed)
    def loudness(self):
        return self._paths.get("loudness", "")

    @Property(str, notify=changed)
    def spectrum(self):
        return self._paths.get("spectrum", "")

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Slot()
    def refresh(self):
        render = dict(self.bridge.lastRender or {})
        if not render:
            return
        self._version += 1
        self._busy, self._status = True, "Drawing the pictures…"
        self.changed.emit()
        self._threads = [t for t in self._threads if t.is_alive()]
        t = threading.Thread(target=self._work, args=(self._version, render), daemon=True)
        self._threads.append(t)
        t.start()

    def close(self):
        """Wait for a drawing in flight (it must not signal a deleted object), then remove our own folder."""
        self._closed = True
        for t in self._threads:
            t.join(timeout=20)
            if t.is_alive():
                print(f"listen pictures: a drawing is still running after 20 s ({self._folder})")
        if self._own:
            shutil.rmtree(self._folder, ignore_errors=True)

    def _work(self, version, render):
        try:
            out = (make_pictures(render, self._folder, version), "")
        except Exception as e:  # noqa: BLE001  shown on the panel, whatever it was
            out = ({}, f"Could not draw the pictures: {type(e).__name__}: {e}")
        if not self._closed:
            self._done.emit(version, *out)

    def _finish(self, version, paths, error):
        if version != self._version:                 # a newer render is already being drawn
            return
        self._busy, self._status = False, error
        if not error:
            self._paths = paths
        self.changed.emit()
