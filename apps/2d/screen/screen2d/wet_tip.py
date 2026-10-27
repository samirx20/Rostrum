"""The wet ink's tip (wet_ink.py): the stroke's newest points, from `start` on, drawn piece by piece.

Each look stamps only the points that came since the last one (from the last drawn point on, so the line joins),
carrying on the stroke's coverage (`carry`: where a piece overlaps the last nothing is laid twice, so a see-through
brush shows no beads at the joins). A move costs its own few px, never the whole tip again. The canvas lies in world
px from `at` and grows (by half its size a side, at least GROW px, at most a few brush widths; a smear's within its
canvas) when a point leaves it, so it is rarely made again. Its picture is made only
when something was drawn since the last, from its straight pixels (`u8`), which each piece updates only where it lies.
A smudge's tip (`base`) smears the paint under it: its canvas starts as that paint (base(x0, y0, x1, y1): premultiplied
px of that box), so each piece smears what the last one left, and a move costs its own dabs however long the tip is.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage

GROW = 64                   # the least px of room the canvas gains round the points when it grows


class Tip:
    def __init__(self, start: int, base=None):
        self.start, self.done = start, start        # the stroke's points from `start` on; how many are drawn
        self.base = base                            # a smudge's: the paint it smears, by box (None: nothing)
        self.px = self.cov = self.u8 = None         # the canvas (premultiplied), the stroke's coverage, the straight px
        self.at = (0, 0)                            # the canvas's top-left, world px
        self.used = None                            # (x0, y0, x1, y1) world px drawn on so far
        self._pic = None

    def drawn(self, ink, points: list) -> "Tip":
        """The points not yet drawn stamped in (`ink`: the WetInk, its brush and box)."""
        if len(points) <= self.done:
            return self
        at = max(self.start, self.done - 1)
        new = points[at:]
        box = ink._box(new)
        if box is not None:
            self._room(box, ink)
            ink._stamp(self.px, self.at, new, self.cov, first=at == 0)
            ax, ay = self.at
            self.u8[box[1] - ay:box[3] - ay, box[0] - ax:box[2] - ax] = ink.straight(
                self.px, (box[0] - ax, box[1] - ay, box[2] - ax, box[3] - ay), box[:2])
            u = self.used
            self.used = box if u is None else (min(u[0], box[0]), min(u[1], box[1]), max(u[2], box[2]), max(u[3], box[3]))
            self._pic = None
        self.done = len(points)
        return self

    def _room(self, box, ink):
        bx0, by0, bx1, by1 = box
        if self.px is not None:
            ax, ay = self.at
            h, w = self.cov.shape
            if bx0 >= ax and by0 >= ay and bx1 <= ax + w and by1 <= ay + h:
                return
            x0, y0, x1, y1 = min(bx0, ax), min(by0, ay), max(bx1, ax + w), max(by1, ay + h)
        else:
            ax, ay, w, h = bx0, by0, 0, 0
            x0, y0, x1, y1 = box
        # room for the line to go on: half the canvas, at most a few brush widths (half of everything each time made a
        # long stroke's canvas double: 6184 x 4417 px for an 1800 px sweep), never past a smear's canvas; only on the
        # sides the points left it by (room on every side at each growth made a level sweep's canvas 4288 px tall, and
        # each growth copied all of it: a 260 px brush's piece took 145-520 ms, so the ink trailed the pen)
        most = max(GROW, int(4 * ink.reach))
        gx, gy = max(GROW, min(most, (x1 - x0) // 2)), max(GROW, min(most, (y1 - y0) // 2))
        first = self.px is None
        nx, ny = x0 - gx if first or bx0 < ax else x0, y0 - gy if first or by0 < ay else y0
        ex, ey = x1 + gx if first or bx1 > ax + w else x1, y1 + gy if first or by1 > ay + h else y1
        if ink.bounds is not None:
            nx, ny, ex, ey = max(0, nx), max(0, ny), min(ink.bounds[0], ex), min(ink.bounds[1], ey)
        px = (np.zeros((ey - ny, ex - nx, 4), np.float32) if self.base is None else self.base(nx, ny, ex, ey))
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
