"""The pen's lean, from Qt's tablet events: the canvas' PointHandler gives pressure but not tilt, so the window's events
are watched before Qt Quick hands them on. `lean()` is the pen's lean each way in degrees (Qt's xTilt / yTilt, x right,
y down: the screen's and the composition's directions, the view only zooms and pans) while a pen is drawing, None for a
mouse or a pen without tilt. `has_tilt` says a tilting pen is connected (one is listed, or one has leaned): the brush
panel shows Tilt → angle / size only then. The painting kit takes the lean as each point's 4th and 5th numbers
(rostrum_paint/shape.py); strokes.py turns it into the canvas' own directions.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QInputDevice, QPointingDevice
from rostrum_gui.gui_filter import GuiFilter

PEN_TYPES = {QInputDevice.DeviceType.Stylus, QInputDevice.DeviceType.Airbrush}
TABLET = {QEvent.Type.TabletPress, QEvent.Type.TabletMove, QEvent.Type.TabletRelease}


def _tilts(device) -> bool:
    return device is not None and bool(device.capabilities() & QInputDevice.Capability.XTilt)


class PenTilt(GuiFilter):
    changed = Signal()              # has_tilt changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lean, self.has_tilt = None, any(_tilts(d) for d in QInputDevice.devices())

    def lean(self):
        return self._lean

    def on_event(self, obj, ev):
        t = ev.type()
        if t in TABLET:
            device = ev.pointingDevice()
            tilts = _tilts(device) or ev.xTilt() != 0 or ev.yTilt() != 0
            self._lean = (round(ev.xTilt(), 2), round(ev.yTilt(), 2)) if tilts else None
            if tilts and not self.has_tilt:
                self.has_tilt = True
                self.changed.emit()
        elif t == QEvent.Type.MouseButtonPress:     # a mouse (not a pen's own press, which Qt may pass on as a mouse's)
            device = ev.pointingDevice()
            if not isinstance(device, QPointingDevice) or device.type() not in PEN_TYPES:
                self._lean = None
        return False
