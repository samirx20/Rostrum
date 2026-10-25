"""The Sound bridge's signals in one place, so the slot mix-ins (view_slots.py, picture_slots.py …) can name them
in their properties' `notify`. A plain class, listed among SoundBridge's bases (gui-kit README › parts.py)."""
from __future__ import annotations

from PySide6.QtCore import Signal


class SoundSignals:
    timeChanged = Signal()
    playingChanged = Signal()
    timelineChanged = Signal()      # the arrangement's layout (`tracks`: rows without their blocks), not a block's edit
    markersChanged = Signal()       # the markers only: a note's edit leaves every marker flag as it is
    rollChanged = Signal()          # the Editor's piano roll's layout (another track, kind, keys): the rows stay
    rollBlocksChanged = Signal()    # the roll's notes / hits / clips only (an edit on them): its layout stays
    rollPatched = Signal(str)                       # a change of them: one patch, JSON text (block_patch.py)
    rollPickedChanged = Signal()    # the roll's selected blocks (`rollPicked`): a pick, or an edit on one of them
    blocksPatched = Signal(str, str)                # a change of an arrangement row's: (row id, patch text, block_patch.py)
    blocksReset = Signal(str)       # that row's whole list again: the screen drops its patch
    pictureChanged = Signal()       # the picture corner's choice, start or render (picture_slots.py)
    renderChanged = Signal()
    soundChanged = Signal()
    viewChanged = Signal()
    pictureOpenChanged = Signal()
    pointChanged = Signal()
