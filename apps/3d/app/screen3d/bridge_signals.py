"""Bridge3D's signals, in one place so each mix-in's properties can name theirs as `notify` (a mix-in of Bridge3D)."""
from PySide6.QtCore import Signal


class Signals3D:
    frameChanged = Signal()
    outlineChanged = Signal()
    playingChanged = Signal()
    markersChanged = Signal()
    pageChanged = Signal()
    shotChanged = Signal()              # the screen shows another shot (showShot): the viewport starts from its camera
