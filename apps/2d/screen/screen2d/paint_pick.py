"""Hold Alt while Draw is on: the pointer picks the colour under it (UX_SPEC.md §3.8, Keys). The colour is the one in the
engine's frame the canvas shows (what the person sees, not a guess from layer data); a click makes it the brush's colour,
as typing it into the bar's Colour does (`painter.setValue("color", …)`); letting go of Alt goes back to painting.
The Brush panel's Pick (I) arms the same pick without Alt (`arm`): one click picks, then the brush is back.
A QObject part, read in QML as `backend.colourPick`. The Alt key is read for the whole window by an event filter here
(a lone modifier key has no key event on an item without the keyboard focus).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QEvent, QObject, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication


class ColourPick(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._alt, self._at, self._swatch, self._armed = bridge, False, (0.0, 0.0), "", False
        app = QGuiApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        bridge.toolChanged.connect(lambda: (self.setAlt(False), self.arm(False)))

    alt = Property(bool, lambda self: (self._alt or self._armed) and self.b.tool == "draw", notify=changed)
    armed = Property(bool, lambda self: self._armed, notify=changed)       # Pick (I) is the tool, not Alt held
    swatch = Property(str, lambda self: self._swatch if self._alt or self._armed else "", notify=changed)    # the colour under the pointer
    at = Property("QVariantMap", lambda self: {"x": self._at[0], "y": self._at[1]}, notify=changed)   # where, composition px

    @Slot(float, float)
    def look(self, x, y):
        """The pointer is at (x, y) (composition px): while Alt is held the swatch shows the colour there."""
        self._at, self._swatch = (x, y), self.colour_at(x, y) if self._alt or self._armed else ""
        self.changed.emit()

    def eventFilter(self, obj, event):          # noqa: N802 (Qt's name)
        t = event.type()
        if t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease) and event.key() == Qt.Key.Key_Alt:
            self.setAlt(t == QEvent.Type.KeyPress)
        elif t == QEvent.Type.WindowDeactivate:
            self.setAlt(False)
        return False

    @Slot(bool)
    def arm(self, on):
        if on != self._armed:
            self._armed = on
            self.look(*self._at)

    @Slot(bool)
    def setAlt(self, on):
        """Alt held (a script says so with the `altpick` step)."""
        if on != self._alt:
            self._alt = on
            self.look(*self._at)

    def colour_at(self, x: float, y: float) -> str:
        """The colour of the frame the canvas shows at composition point (x, y), "#rrggbb"; "" where the frame is clear
        (nothing painted there) or the point is off the frame."""
        image = self.b.frames.provider.requestImage("", None, None)
        info = self.b.frameInfo
        if image.isNull() or not info["width"]:
            return ""
        px, py = int(x * image.width() / info["width"]), int(y * image.height() / info["height"])
        if not (0 <= px < image.width() and 0 <= py < image.height()):
            return ""
        c = image.pixelColor(px, py)
        return "" if c.alpha() < 128 else c.name()

    @Slot(float, float, result=str)
    def colourAt(self, x, y):
        return self.colour_at(x, y)

    @Slot(float, float, result=bool)
    def pickAt(self, x, y):
        """A click with Alt held: the colour there becomes the brush colour (and says so in the status line)."""
        c = self.colour_at(x, y)
        if not c:
            self.b._set_status("Nothing to pick there: the frame is clear")
            return False
        ok = self.b.painter.setValue("color", c)
        self.arm(False)                         # Pick picks once, then the brush is back
        if ok:
            self.b._set_status(f"Brush colour {c}")
        return ok
