"""Python's cycle collector kept from pausing the screen. Its full collection walks every object alive: on the critic's
piece (the document, its history, the screen's QML wrappers) one took ~35 ms, landing in the middle of an edit or a
drag. Once a document is open and the person pauses, everything alive then is collected once and set aside
(gc.freeze): later collections walk only what came after. Each open sets aside again, after letting the last open's
objects back in (gc.unfreeze), so a closed document's cycles are still freed. Nothing changes in what is kept or freed
by reference counting; only when the walk happens."""
from __future__ import annotations

import gc

from PySide6.QtCore import QTimer

from . import pointer_quiet

AFTER_MS = 1500     # after a document is shown: its first frames, fonts and pictures are made by then


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
