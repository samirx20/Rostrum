"""The Sound bridge's signals in one place, so the slot mix-ins (view_slots.py, picture_slots.py …) can name them
in their properties' `notify`. A plain class, listed among SoundBridge's bases (gui-kit README › parts.py)."""
from __future__ import annotations

from PySide6.QtCore import Signal


class SoundSignals:
    timeChanged = Signal()
    playingChanged = Signal()
    timelineChanged = Signal()
    renderChanged = Signal()
    soundChanged = Signal()
    viewChanged = Signal()
    pictureOpenChanged = Signal()
    pointChanged = Signal()
