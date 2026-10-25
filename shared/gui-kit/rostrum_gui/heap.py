"""Python's cycle collector kept from pausing the screen. Its full collection walks every object alive: on the critic's
piece (the document, its history, the screen's QML wrappers) one took ~35 ms, landing in the middle of an edit or a
drag. Once a document is open and the person pauses, everything alive then is collected once and set aside
(gc.freeze): later collections walk only what came after. Each open sets aside again, after letting the last open's
objects back in (gc.unfreeze), so a closed document's cycles are still freed. Nothing changes in what is kept or freed
by reference counting; only when the walk happens.

Edits keep adding: a whole-song change leaves ~10,000 new objects (the song's new version, its blocks), and every full
collection walks all that came since the last set-aside (one took ~58 ms inside a key, sound-speed r6). `after_edit()`:
once the person pauses, what is alive is set aside again without a walk (gc.freeze alone moves it); after a longer
rest, one full calm, so cycles made while editing are still freed."""
from __future__ import annotations

import gc

from PySide6.QtCore import QTimer

from . import pointer_quiet

AFTER_MS = 1500     # after a document is shown: its first frames, fonts and pictures are made by then
PAUSE_MS = 700      # after an edit: set aside without a walk
REST_MS = 8000      # after an edit and no other: the full calm (unfreeze, collect, freeze)
_TIMERS: list = []


def calm_later(ms: int = AFTER_MS):
    QTimer.singleShot(ms, _calm)


def _calm():
    if pointer_quiet.busy():                 # never beside a click or a drag: once the pointer rests
        return QTimer.singleShot(500, _calm)
    calm_now()


def calm_now():
    """Collect and set aside now (a measuring step starts from the state a person meets after a pause)."""
    gc.unfreeze()
    gc.collect()
    gc.freeze()


def after_edit():
    """An edit just landed (call on each change): set aside after a pause, the full calm after a rest. A newer edit
    starts both waits again."""
    if not _TIMERS:
        for ms, fn in ((PAUSE_MS, gc.freeze), (REST_MS, calm_now)):
            _TIMERS.append(QTimer(singleShot=True, interval=ms, timeout=lambda fn=fn: _quietly(fn)))
    for t in _TIMERS:
        t.start()


def _quietly(fn):
    if pointer_quiet.busy():                 # never beside a click or a drag
        return QTimer.singleShot(500, lambda: _quietly(fn))
    fn()
