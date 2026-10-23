"""The one way an app puts its own data on the clipboard (layers, strokes, keys …): `put({mime type: bytes}, text)`.

A QMimeData made in Python is a Python-backed object the clipboard then owns. With a real system clipboard (Windows,
macOS) Qt hands it over and frees it while the app shuts down. With no system clipboard (the "offscreen" / "minimal"
platforms that scripted runs and tests use) Qt keeps it in a process-wide store that is freed only after Python has
finished, and freeing it then crashes the process at exit. So on those platforms the clipboard is emptied while Python
still runs (atexit): its data could not outlive the process anyway. A real clipboard is left alone, so a copy still
pastes into other apps after Rostrum closes.
"""
from __future__ import annotations

import atexit

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QGuiApplication

_IN_PROCESS = {"offscreen", "minimal"}     # platforms whose clipboard lives only inside this process
_armed = False


def put(formats: dict[str, bytes], text: str | None = None) -> None:
    """Replace the clipboard with these formats (and plain text, if given)."""
    global _armed
    if not isinstance(QGuiApplication.instance(), QGuiApplication):
        raise RuntimeError("the clipboard needs a QGuiApplication; this process has none (or a screen-less QCoreApplication)")
    mime = QMimeData()
    for kind, data in formats.items():
        mime.setData(kind, data)
    if text is not None:
        mime.setText(text)
    QGuiApplication.clipboard().setMimeData(mime)
    if not _armed and QGuiApplication.platformName() in _IN_PROCESS:
        _armed = True
        atexit.register(_release)


def _release() -> None:
    if QGuiApplication.instance() is not None:
        QGuiApplication.clipboard().clear()
