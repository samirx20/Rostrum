"""One stroke's wet ink (wet.py shows it): stamped by the painting kit's own brush (`canvas.stamp`, the stamp a saved
stroke gets), in world px (the endless canvas: anywhere, the frame at home or not, negative px too), so no pointer move
waits for the scene to be described and drawn again. Only the stroke's own box is ever held, never the composition.

The stroke is drawn piece by piece (wet_tip.py) on its own thread (`_TIP`): the kit lays one stroke in pieces, each
piece the dabs not laid yet, so a piece costs its own few dabs however long the stroke is, and the screen's thread only
shows the newest finished one. The pieces are the saved stroke's own pixels (its draws are per dab, its ragged start
sized in brush sizes), so nothing is ever stamped again: at the lift (`lift`) the closing piece lays the end, the only
part the saved stroke draws differently (its taper and ragged end come only once it has an end).

`under`: a smudging brush smears the layer's own paint (premultiplied, its canvas px: `bounds` is the canvas size and
the smear stays inside it, points in canvas px, `place` = (x, y, x scale, y scale) puts canvas px on the world). It is
only read, never copied whole (a big drawing's copy at each press cost tens of ms): the tip smears a copy of the boxes
it reaches (wet_tip.Tip's `base`), piece by piece. `under`
may be a Future (the paint still being made off the screen's thread: wet.smear_ink): the smear shows once it is done
(`ready`), the points that came meanwhile with it, so the press never waits for a drawing's pixels.
A smear's pictures hold the layer's paint with the smear in it, so they replace that paint rather than lie on it:
laid on the frame that shows it already, see-through paint would count twice (a brighter box: critic r12). Once its
layer holds paint (`covers`, set by the screen when it asks for the reveal) a smear shows over the world drawn under
its layer, and waits for that picture (`reveal`; the screen lays it under the wet boxes and the layers above over them:
wet_layers.py; blending it here cost each tip piece 20-120 ms, so a big smear trailed the pen). Points past a drawing's canvas are fine: a drawing grows
with the stroke (no `bounds`); what lies outside the paint under it is empty.
Normal ink has no bounds (None). `reveal`: the eraser. Its ink is the eraser's coverage, and where it lies the picture
shows the world drawn without the layer being erased (straight RGBA8 at 1 px per world px, its top-left at world px
`origin`: `reveal_with`): over the canvas that is (1 - e) × with + e × without, exactly what erasing e of a layer's
paint gives (its blend is linear in the paint's alpha). Until that picture comes, and outside it, nothing shows.
"""
from __future__ import annotations

import math
from concurrent.futures import Future, ThreadPoolExecutor

import numpy as np
from PySide6.QtGui import QImage
from rostrum_paint import canvas, native
from rostrum_paint.ops import build, seed_of

from .wet_tip import Tip

PAD = 4                     # px round the stroke's box, for the brush's soft edge and jitter
_TIP = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wet-tip")     # the stroke's pieces (`tip`)


class WetInk:
    def __init__(self, brush: dict, sid: str, scale: float, bounds: tuple[int, int] | None, under: np.ndarray | None = None,
                 place=(0.0, 0.0, 1.0, 1.0), erasing: bool = False, done=None):
        self.erasing = erasing
        self.brush = {**brush, "mode": "normal", "smudge": False} if erasing else brush   # an eraser: its coverage
        self.sid, self.scale, self.bounds = sid, scale or 1.0, bounds
        self.size = brush.get("size", 10) / self.scale
        self.reach = self.size / 2 + PAD + 3 * brush.get("jitter", 0) * self.size
        self.points: list[list[float]] = []
        self.smears, self.place, self.reveal, self._origin = under is not None, place, None, (0, 0)
        self.covers = erasing                                           # shows over the world without its layer
        self._coming = under if isinstance(under, Future) else None    # the paint under a smear, still being made
        if self._coming is not None:
            under = None
            if done is not None:
                self._coming.add_done_callback(lambda _f: done())
        self.shift = (0.0, 0.0)                                         # added to each point (a smear's tile: wet_through.py)
        self._base = under                                              # what the stroke starts on (None: nothing; read only)
        self._done, self._lifted = done, False                          # called when a piece is done; the pen is up
        self._tip_now = None                                            # the stroke drawn so far (wet_tip.Tip)
        self._tip_pic, self._tip_job = None, None                       # its newest picture; its piece running

    @property
    def ready(self) -> bool:
        """Whether there is anything to show yet (an eraser waits for the frame without its layer, a smear for the
        paint it smears: a failure to make it raises here, on the screen's thread)."""
        if self._coming is not None:
            if not self._coming.done():
                return False
            self._base, self._coming = self._coming.result(), None
        return not self.covers or self.reveal is not None

    def reveal_with(self, frame: np.ndarray, origin: tuple[int, int]):
        self.reveal, self._origin = frame, origin

    def add(self, x: float, y: float, pressure: float):
        self.points.append([x + self.shift[0], y + self.shift[1], round(min(max(pressure, 0.0), 1.0), 3)])

    def _box(self, pts) -> tuple[int, int, int, int] | None:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x0, y0 = math.floor(min(xs) - self.reach), math.floor(min(ys) - self.reach)
        x1, y1 = math.ceil(max(xs) + self.reach), math.ceil(max(ys) + self.reach)
        if self.bounds is not None:                                     # a smear stays on its canvas
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(self.bounds[0], x1), min(self.bounds[1], y1)
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    def _stamp(self, into, origin, pts, carry, piece):
        """The stroke so far `pts` laid into `into` (its top-left at `origin`) in pieces: brush.stamp_stroke's `carry`
        and `piece` (the kit leaves out the end's taper and raggedness while the piece is open). Its Coverage or None."""
        item = build("stroke", self.sid, {**self.brush, "size": self.size, "seed": seed_of(self.sid),
                                          "points": [[x - origin[0], y - origin[1], p] for x, y, p in pts]})
        # what is under the stroke, only for a brush that picks it up (a copy of the canvas: a big tip's cost tens of ms)
        under = into.copy()[..., :3] if item["smudge"] and item["pickup"] else None
        return canvas.stamp(into, item, into.shape[1], into.shape[0], {}, under, carry=carry, piece=piece)

    def _smeared(self):
        """A smear's paint as its tip finds it, by box (canvas px; nothing outside the canvas). None for ink that
        smears nothing."""
        if not self.smears:
            return None
        under = self._base

        def base(x0, y0, x1, y1):
            out = np.zeros((y1 - y0, x1 - x0, 4), np.float32)
            cx0, cy0, cx1, cy1 = max(x0, 0), max(y0, 0), min(x1, under.shape[1]), min(y1, under.shape[0])
            if cx1 > cx0 and cy1 > cy0:
                out[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0] = under[cy0:cy1, cx0:cx1]
            return out
        return base

    def lift(self):
        """The pen is up: the next piece is the closing one, laying the stroke's end (its taper and ragged end)."""
        self._lifted = True

    @property
    def whole(self) -> bool:
        """Every point is drawn and shown, the end too (nothing running): a lifted stroke's ink has nothing more to
        draw."""
        shown, tip = self._tip_pic, self._tip_now
        return (self._lifted and self._tip_job is None and shown is not None and tip is not None and tip.closed
                and tip.done >= len(self.points))

    def tip(self) -> tuple[QImage, dict] | None:
        """The stroke's newest picture. Its pieces are stamped on their own thread (`_TIP`), one at a time, each with
        the dabs not laid yet: a big brush's dabs cost milliseconds each, so the pen's moves never wait for them (a
        260 px brush cost 40-80 ms a move on the screen's thread: critic r12). A finished piece shows at the next look
        (it asks for one: `done`). A piece that failed raises here, on the screen's thread."""
        if self._tip_now is None:
            self._tip_now = Tip(self._smeared())
        job, tip = self._tip_job, self._tip_now
        if job is not None and job.done():
            self._tip_job = None
            self._tip_pic = job.result()
        if self._tip_job is None and self.points and (len(self.points) > tip.done or self._lifted and not tip.closed):
            pts, open_ = self.points[:], not self._lifted
            self._tip_job = _TIP.submit(lambda: tip.drawn(self, pts, open_).picture(self))
            if self._done is not None:
                self._tip_job.add_done_callback(lambda _f: self._done())
        return self._tip_pic

    def straight(self, px, box, at, out=None) -> np.ndarray:
        """Premultiplied px's part `box` (x0, y0, x1, y1) as a picture's straight RGBA8 (h x w x 4; into `out` if
        given), `at`: where `box` lies, world px; an eraser's: the frame without its layer there, as much as the
        eraser covers."""
        x0, y0, x1, y1 = box
        if self.erasing:
            u8 = self._revealed(at[0], at[1], x1 - x0, y1 - y0)
            u8[..., 3] = np.minimum(u8[..., 3], np.clip(px[y0:y1, x0:x1, 3] * 255 + 0.5, 0, 255).astype(np.uint8))
            if out is not None:
                out[...] = u8
            return u8
        return native.straight8(px[y0:y1, x0:x1], out=out)   # (a smear's lies on the world under its layer: wet_layers.py)

    def moved(self, image: QImage, box: dict, dx: float, dy: float) -> QImage:
        """An eraser's picture (box: where it lies, world px) as it shows moved by dx, dy: the same coverage, and there
        the world without the layer at that place (a seamless painting's wrapped copy: wet_wrap.py)."""
        w, h = image.width(), image.height()
        a = np.frombuffer(image.constBits(), np.uint8).reshape(h, image.bytesPerLine())[:, :w * 4].reshape(h, w, 4)[..., 3]
        u8 = self._revealed(round(box["x"] + dx), round(box["y"] + dy), w, h)
        u8[..., 3] = np.minimum(u8[..., 3], a)
        return QImage(u8.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()

    def _revealed(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        """The reveal picture under the ink's px x, y, w × h (laid on the world by `place`: the eraser's px are world
        px, a smear's its canvas's), the nearest world px to each; where it doesn't reach, see-through (alpha 0)."""
        out = np.zeros((h, w, 4), np.uint8)
        ox, oy, kx, ky = self.place
        H, W = self.reveal.shape[:2]
        cols = np.floor(ox + (x + np.arange(w) + 0.5) * kx).astype(np.int64) - self._origin[0]
        rows = np.floor(oy + (y + np.arange(h) + 0.5) * ky).astype(np.int64) - self._origin[1]
        ci, ri = np.flatnonzero((cols >= 0) & (cols < W)), np.flatnonzero((rows >= 0) & (rows < H))
        if len(ci) and len(ri):
            out[ri[0]:ri[-1] + 1, ci[0]:ci[-1] + 1, :3] = self.reveal[rows[ri][:, None], cols[ci]][..., :3]
            out[ri[0]:ri[-1] + 1, ci[0]:ci[-1] + 1, 3] = 255
        return out

    def _placed(self, image, box):
        ox, oy, kx, ky = self.place
        return image, {"x": ox + box["x"] * kx, "y": oy + box["y"] * ky, "w": box["w"] * kx, "h": box["h"] * ky}
