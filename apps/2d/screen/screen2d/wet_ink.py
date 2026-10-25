"""One stroke's wet ink (wet.py shows it): stamped by the painting kit's own brush (`canvas.stamp`, the stamp a saved
stroke gets), in world px (the endless canvas: anywhere, the frame at home or not, negative px too), so no pointer move
waits for the scene to be described and drawn again. Only the stroke's own box is ever held, never the composition.

Two parts. The tip, the newest points, is drawn on the screen's thread piece by piece (wet_tip.py): each look
stamps only the points that came since the last, carrying on the stroke's coverage, so a move costs its own few px
however long the tip is. The dry part is the whole stroke so far stamped again as the saved stroke will be (a
brush's dabs depend on the whole stroke: its noise and tapers are sized by its length), so the tip never leaves a
seam. That costs the whole stroke, so it runs on a worker thread (`_DRY`): once the tip is CHUNK points long the
next restamp starts, and the screen takes it in at the first look after it is done (`settle`), with the tip from
there already drawn by the worker (the points that came meanwhile). The pen never waits for it.

`under`: a smudging brush smears the layer's own paint (premultiplied, its canvas px: `bounds` is the canvas size and
the smear stays inside it, points in canvas px, `place` = (x, y, x scale, y scale) puts canvas px on the world).
Normal ink has no bounds (None). `reveal`: the eraser. Its ink is the eraser's coverage, and where it lies the picture
shows the world drawn without the layer being erased (straight RGBA8 at 1 px per world px, its top-left at world px
`origin`: `reveal_with`): over the canvas that is (1 - e) × with + e × without, exactly what erasing e of a layer's
paint gives (its blend is linear in the paint's alpha). Until that picture comes, and outside it, nothing shows.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PySide6.QtGui import QImage
from rostrum_paint import canvas, compose
from rostrum_paint.ops import build, seed_of

from .wet_tip import Tip, picture_of

PAD = 4                     # px round the stroke's box, for the brush's soft edge and jitter
CHUNK = 12                  # tip points before the dry part is stamped again (off the screen's thread)
_DRY = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wet-dry")


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
        self.shift = (0.0, 0.0)                                         # added to each point (a smear's tile: wet_through.py)
        self._base = under                                              # what the stroke starts on (None: nothing)
        self._dry = under.copy() if under is not None else None        # a smear's paint so far (its tip smears it)
        self._settled, self._dry_box, self._dry_pic = 0, None, None     # points in the dry part; its box; its picture
        self._job, self._done = None, done                              # the restamp running; called when it is done
        self._tip_now = None                                            # the tip drawn so far (wet_tip.Tip)

    @property
    def ready(self) -> bool:
        """Whether there is anything to show yet (an eraser waits for the frame without its layer)."""
        return not self.erasing or self.reveal is not None

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

    def _tip(self) -> list:
        return self.points[max(0, self._settled - 1):]

    def _stamp(self, into, origin, pts, carry=None):
        item = build("stroke", self.sid, {**self.brush, "size": self.size, "seed": seed_of(self.sid),
                                          "points": [[x - origin[0], y - origin[1], p] for x, y, p in pts]})
        canvas.stamp(into, item, into.shape[1], into.shape[0], {}, into[..., :3].copy() if item["smudge"] else None,
                     carry=carry)

    def _restamp(self, pts, box, base):
        """(worker thread) The whole stroke `pts` stamped again into its box, on what it starts on, and its picture;
        and the tip from its last point on, with the points that came meanwhile (so the screen never draws them)."""
        x0, y0, x1, y1 = box
        part = base if base is not None else np.zeros((y1 - y0, x1 - x0, 4), np.float32)
        self._stamp(part, (x0, y0), pts)
        tip = None if self.smears else Tip(len(pts) - 1).drawn(self, self.points[:])
        return part, self._placed(*self._picture(part, (0, 0, x1 - x0, y1 - y0), (x0, y0))), tip

    def settle(self) -> bool:
        """Takes in a finished restamp of the dry part (True: it changed), and starts the next one once the tip is
        CHUNK points long. A restamp that failed raises here, on the screen's thread."""
        changed = False
        if self._job is not None and self._job[0].done():
            future, box, n = self._job
            self._job = None
            x0, y0, x1, y1 = box
            part, self._dry_pic, tip = future.result()
            if tip is not None:
                self._tip_now = tip
            if self._dry is not None:
                self._dry[y0:y1, x0:x1] = part
            self._dry_box, self._settled, changed = box, n, True
        if self._job is None and len(self._tip()) >= CHUNK:
            pts, box = [list(p) for p in self.points], self._box(self.points)
            if box is not None:
                x0, y0, x1, y1 = box
                base = self._base[y0:y1, x0:x1].copy() if self._base is not None else None
                future = _DRY.submit(self._restamp, pts, box, base)
                self._job = (future, box, len(pts))
                if self._done is not None:
                    future.add_done_callback(lambda _f: self._done())
        return changed

    def dry(self) -> tuple[QImage, dict] | None:
        return self._dry_pic

    def tip(self) -> tuple[QImage, dict] | None:
        if not self.smears:                 # a smudge's tip smears the dry paint afresh (its reservoir runs the tip)
            start = max(0, self._settled - 1)
            if self._tip_now is None or self._tip_now.start != start:
                self._tip_now = Tip(start)
            return self._tip_now.drawn(self, self.points[:]).picture(self)
        tip = self._tip()
        box = self._box(tip) if tip else None
        if box is None:
            return None
        x0, y0, x1, y1 = box
        px = (self._dry[y0:y1, x0:x1].copy() if self.smears        # a smudge's tip: the picture there, smeared
              else np.zeros((y1 - y0, x1 - x0, 4), np.float32))
        self._stamp(px, (x0, y0), tip)
        return self._placed(*self._picture(px, (0, 0, x1 - x0, y1 - y0), (x0, y0)))

    def _picture(self, px, box, at=None) -> tuple[QImage, dict]:
        """The part `box` (x0, y0, x1, y1) of premultiplied pixels as a straight-alpha picture, and where it goes; an
        eraser's: the frame without its layer there, as much as the eraser covers."""
        x0, y0, x1, y1 = box
        ax, ay = at or (x0, y0)
        return picture_of(self.straight(px, box, (ax, ay))), {"x": ax, "y": ay, "w": x1 - x0, "h": y1 - y0}

    def straight(self, px, box, at) -> np.ndarray:
        """The pixels of _picture (straight RGBA8, h x w x 4), `at`: where `box` lies, world px."""
        x0, y0, x1, y1 = box
        if self.erasing:
            u8 = self._revealed(at[0], at[1], x1 - x0, y1 - y0)
            u8[..., 3] = np.minimum(u8[..., 3], np.clip(px[y0:y1, x0:x1, 3] * 255 + 0.5, 0, 255).astype(np.uint8))
            return u8
        return compose.straight8(px[y0:y1, x0:x1])

    def moved(self, image: QImage, box: dict, dx: float, dy: float) -> QImage:
        """An eraser's picture (box: where it lies, world px) as it shows moved by dx, dy: the same coverage, and there
        the world without the layer at that place (a seamless painting's wrapped copy: wet_wrap.py)."""
        w, h = image.width(), image.height()
        a = np.frombuffer(image.constBits(), np.uint8).reshape(h, image.bytesPerLine())[:, :w * 4].reshape(h, w, 4)[..., 3]
        u8 = self._revealed(round(box["x"] + dx), round(box["y"] + dy), w, h)
        u8[..., 3] = np.minimum(u8[..., 3], a)
        return QImage(u8.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()

    def _revealed(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        """The reveal picture over world px x, y, w × h; where it doesn't reach, see-through (alpha 0)."""
        out = np.zeros((h, w, 4), np.uint8)
        rx, ry = x - self._origin[0], y - self._origin[1]
        H, W = self.reveal.shape[:2]
        sx0, sy0, sx1, sy1 = max(0, rx), max(0, ry), min(W, rx + w), min(H, ry + h)
        if sx1 > sx0 and sy1 > sy0:
            out[sy0 - ry:sy1 - ry, sx0 - rx:sx1 - rx, :3] = self.reveal[sy0:sy1, sx0:sx1, :3]
            out[sy0 - ry:sy1 - ry, sx0 - rx:sx1 - rx, 3] = 255
        return out

    def _placed(self, image, box):
        ox, oy, kx, ky = self.place
        return image, {"x": ox + box["x"] * kx, "y": oy + box["y"] * ky, "w": box["w"] * kx, "h": box["h"] * ky}
