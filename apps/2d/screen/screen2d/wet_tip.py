"""The wet ink's stroke (wet_ink.py), drawn piece by piece as the pen goes: the painting kit lays one stroke in pieces
(brush.stamp_stroke's `piece`, one `brush.Carry` from piece to piece), each piece the dabs not laid yet, so the pieces
give the pixels the saved stroke gets (its draws are per dab: `by_dab`) and a move costs its own few dabs however long
the stroke is. While the pen is down the dab at the pen waits (`held`: world px; the next piece's room reaches back to
it) and the end has no taper or raggedness; the closing piece (`drawn(..., open_=False)`, at the lift) lays them.
The canvas lies in world px from `at` and grows (by half its size a side, at least GROW px, at most a few brush
widths; a smear's within its canvas) when a point leaves it, so it is rarely made again. Its picture is made only
when something was drawn since the last, from its straight pixels (`u8`), which each piece updates only where it lies.
A smudge's tip (`base`) smears the paint under it: its canvas starts as that paint (base(x0, y0, x1, y1): premultiplied
px of that box), so each piece smears what the last one left.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage
from rostrum_paint import brush

GROW = 64                   # the least px of room the canvas gains round the points when it grows


class Tip:
    def __init__(self, base=None):
        self.done, self.closed = 0, False           # how many of the stroke's points are drawn; the end laid
        self.base = base                            # a smear's: the paint it smears, by box (None: nothing)
        self.carry = brush.Carry()                  # the coverage laid, the wet reservoir, the next dab
        self.held = None                            # world px of the next dab (up to a spacing behind the pen)
        self.px = self.u8 = None                    # the canvas (premultiplied), the straight px
        self.at = (0, 0)                            # the canvas's top-left, world px
        self.used = None                            # (x0, y0, x1, y1) world px drawn on so far
        self._pic = None

    def drawn(self, ink, points: list, open_: bool = True) -> "Tip":
        """The dabs not laid yet stamped in (`ink`: the WetInk, its brush and box); `open_` False: the stroke's end."""
        if self.closed or (open_ and len(points) <= self.done):
            return self
        new = points[max(0, self.done - 1):]
        box = ink._box(([self.held] if self.held else []) + new)
        if box is not None:
            self._room(box, ink)
            ax, ay = self.at
            got = ink._stamp(self.px, self.at, points, self.carry, (0, open_))
            ahead = self.carry.ahead
            self.held = None if ahead is None else [ahead[0] + ax, ahead[1] + ay]
            if got is not None:
                x0, y0, x1, y1 = got.bbox                           # canvas px, where this piece laid
                ink.straight(self.px, got.bbox, (x0 + ax, y0 + ay), self.u8[y0:y1, x0:x1])
                w = (x0 + ax, y0 + ay, x1 + ax, y1 + ay)
                u = self.used
                self.used = w if u is None else (min(u[0], w[0]), min(u[1], w[1]), max(u[2], w[2]), max(u[3], w[3]))
                self._pic = None
        self.done, self.closed = len(points), not open_
        return self

    def _room(self, box, ink):
        bx0, by0, bx1, by1 = box
        if self.px is not None:
            ax, ay = self.at
            h, w = self.px.shape[:2]
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
        # the canvas so far copied in, only the strips round it made: empty, a smear's its paint (a long stroke's canvas
        # is tens of MB, so a growth is this piece's biggest cost)
        W, H = ex - nx, ey - ny
        px, cov, u8 = np.empty((H, W, 4), np.float32), np.empty((H, W), np.float32), np.empty((H, W, 4), np.uint8)
        ox0, oy0, ox1, oy1 = ax - nx, ay - ny, ax - nx + w, ay - ny + h
        if self.px is not None:
            px[oy0:oy1, ox0:ox1], u8[oy0:oy1, ox0:ox1] = self.px, self.u8
            cov[oy0:oy1, ox0:ox1] = 0 if self.carry.cov is None else self.carry.cov    # (None: no dab laid yet)
        for x0, y0, x1, y1 in ((0, 0, W, oy0), (0, oy1, W, H), (0, oy0, ox0, oy1), (ox1, oy0, W, oy1)):
            if x1 > x0 and y1 > y0:
                cov[y0:y1, x0:x1] = 0
                if self.base is None:
                    px[y0:y1, x0:x1], u8[y0:y1, x0:x1] = 0, 0
                else:                               # a smear's picture is its paint where no piece has laid yet
                    px[y0:y1, x0:x1] = self.base(nx + x0, ny + y0, nx + x1, ny + y1)
                    ink.straight(px, (x0, y0, x1, y1), (nx + x0, ny + y0), u8[y0:y1, x0:x1])
        self.px, self.u8, self.at = px, u8, (nx, ny)
        self.carry.cov = cov

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
