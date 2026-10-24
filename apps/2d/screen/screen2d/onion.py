"""Onion skin: the neighbouring drawings of the selected drawing layer, tinted (previous red, next green), as one
picture laid over the layer's box on the canvas (image://onion/<n>: the kit's one-picture provider, rostrum_gui.frames.ImageProvider). The pictures come from the painting kit
(`canvas.rgba8` for each frame, `see.onion` to tint and combine), at the drawing's own canvas size (Qt scales it to the box).
"""
from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage
from rostrum2d.drawing import canvas_size, frame_at, neighbours
from rostrum_paint import canvas, see


def build(drawing: dict, n: int, reach_before: int = 2, reach_after: int = 2) -> QImage | None:
    """The tinted neighbours of the drawing shown at frame n (so many each way); None when there are none to show."""
    here = frame_at(drawing, n)
    if here is None:
        return None
    before, after = neighbours(drawing, here["id"], max(reach_before, reach_after))
    before, after = before[:reach_before], after[:reach_after]
    if not before and not after:
        return None
    cw, ch = canvas_size(drawing)
    w, h = cw, ch                 # the kit draws strokes in canvas px: a smaller picture would not scale them
    px = np.ascontiguousarray(see.onion(canvas.rgba8(here, w, h), [canvas.rgba8(f, w, h) for f in before],
                                        [canvas.rgba8(f, w, h) for f in after]), dtype=np.uint8)
    return QImage(px.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()      # copy: px goes away
