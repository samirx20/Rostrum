"""The Sound bridge's signals in one place, so the slot mix-ins (view_slots.py, picture_slots.py …) can name them
in their properties' `notify`. A plain class, listed among SoundBridge's bases (gui-kit README › parts.py)."""
from __future__ import annotations

from PySide6.QtCore import Signal


class SoundSignals:
    timeChanged = Signal()
    playingChanged = Signal()
    timelineChanged = Signal()
    rollChanged = Signal()          # the Editor's piano roll only (a selection on another track): the rows stay
    renderChanged = Signal()
    soundChanged = Signal()
    viewChanged = Signal()
    pictureOpenChanged = Signal()
    pointChanged = Signal()
