"""What a wheel, a touchpad or a pinch does to the viewport's camera (3d-simplicity SPEC §1, "Moving around, in every
tool"): a mouse wheel zooms; a touchpad's two-finger scroll turns the view as a drag would (the view follows the
fingers); a pinch zooms, whether it comes as a gesture (PinchHandler) or, as Windows' precision touchpads send it, as
Ctrl + wheel.

A touchpad is told from a mouse by what it sends: the device says so (when Qt knows), or the scroll has a phase or
pixel steps (macOS), or its steps are not whole wheel notches of 120 (Windows' precision touchpads).
No Qt.
"""
from __future__ import annotations

import math

from .viewcam import ZOOM_STEP

NOTCH = 120                 # angleDelta of one mouse wheel notch
PAD_PX = 0.25               # a touchpad's angleDelta units per pointer pixel of drag


def is_touchpad(ax: float, ay: float, px: float, py: float, phased: bool, device_touchpad: bool) -> bool:
    return device_touchpad or phased or bool(px or py) or bool(ax % NOTCH or ay % NOTCH)


def wheel(ax: float, ay: float, px: float, py: float, phased: bool, ctrl: bool, device_touchpad: bool) -> tuple:
    """("zoom", steps, 0) or ("orbit", dx, dy) in drag pixels for one wheel event."""
    if ctrl or not is_touchpad(ax, ay, px, py, phased, device_touchpad):
        return "zoom", ay / NOTCH, 0.0
    if px or py:
        return "orbit", float(px), float(py)
    return "orbit", ax * PAD_PX, ay * PAD_PX


def pinch_steps(scale: float) -> float:
    """Zoom steps (viewcam.zoom) for a pinch that scaled by `scale` (> 1: fingers apart, nearer)."""
    return math.log(scale) / math.log(1 / ZOOM_STEP)
