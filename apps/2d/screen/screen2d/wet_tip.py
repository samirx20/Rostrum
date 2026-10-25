"""The wet ink's tip (wet_ink.py): the stroke's newest points, from `start` on, drawn piece by piece.

Each look stamps only the points that came since the last one (from the last drawn point on, so the line joins),
carrying on the stroke's coverage (`carry`: where a piece overlaps the last nothing is laid twice, so a see-through
brush shows no beads at the joins). A move costs its own few px, never the whole tip again. The canvas lies in world
px from `at` and grows (by half its size a side, at least GROW px) when a point leaves it, so it is rarely made again. Its picture is made only
when something was drawn since the last, from its straight pixels (`u8`), which each piece updates only where it lies.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage

GROW = 64                   # the least px of room the canvas gains round the points when it grows


class Tip:
    def __init__(self, start: int):
        self.start, self.done = start, start        # the stroke's points from `start` on; how many are drawn
        self.px = self.cov = self.u8 = None         # the canvas (premultiplied), the stroke's coverage, the straight px
        self.at = (0, 0)                            # the canvas's top-left, world px
        self.used = None                            # (x0, y0, x1, y1) world px drawn on so far
        self._pic = None

    def drawn(self, ink, points: list) -> "Tip":
        """The points not yet drawn stamped in (`ink`: the WetInk, its brush and box)."""
        if len(points) <= self.done:
            return self
        new = points[max(self.start, self.done - 1):]
        box = ink._box(new)
        if box is not None:
            self._room(box)
            ink._stamp(self.px, self.at, new, self.cov)
            ax, ay = self.at
            self.u8[box[1] - ay:box[3] - ay, box[0] - ax:box[2] - ax] = ink.straight(
                self.px, (box[0] - ax, box[1] - ay, box[2] - ax, box[3] - ay), box[:2])
            u = self.used
            self.used = box if u is None else (min(u[0], box[0]), min(u[1], box[1]), max(u[2], box[2]), max(u[3], box[3]))
            self._pic = None
        self.done = len(points)
        return self

    def _room(self, box):
        x0, y0, x1, y1 = box
        if self.px is not None:
            ax, ay = self.at
            h, w = self.cov.shape
            if x0 >= ax and y0 >= ay and x1 <= ax + w and y1 <= ay + h:
                return
            x0, y0, x1, y1 = min(x0, ax), min(y0, ay), max(x1, ax + w), max(y1, ay + h)
        gx, gy = max(GROW, (x1 - x0) // 2), max(GROW, (y1 - y0) // 2)      # room for the line to go on
        nx, ny = x0 - gx, y0 - gy
        px = np.zeros((y1 - y0 + 2 * gy, x1 - x0 + 2 * gx, 4), np.float32)
        cov, u8 = np.zeros(px.shape[:2], np.float32), np.zeros(px.shape[:2] + (4,), np.uint8)
        if self.px is not None:
            (ax, ay), (h, w) = self.at, self.cov.shape
            for new, old in ((px, self.px), (cov, self.cov), (u8, self.u8)):
                new[ay - ny:ay - ny + h, ax - nx:ax - nx + w] = old
        self.px, self.cov, self.u8, self.at = px, cov, u8, (nx, ny)

    def picture(self, ink):
        """(picture, where it goes) of what is drawn, or None."""
        if self.used is None:
            return None
        if self._pic is None:
            (x0, y0, x1, y1), (ax, ay) = self.used, self.at
            self._pic = ink._placed(picture_of(self.u8[y0 - ay:y1 - ay, x0 - ax:x1 - ax]),
                                    {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0})
        return self._pic

def picture_of(u8: np.ndarray) -> QImage:
    """Straight RGBA8 pixels (h x w x 4) as a picture of its own."""
    u8 = np.ascontiguousarray(u8)
    h, w = u8.shape[:2]
    return QImage(u8.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
