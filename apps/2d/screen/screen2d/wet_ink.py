"""One stroke's wet ink (wet.py shows it): stamped by the painting kit's own brush (`canvas.stamp`, the stamp a saved
stroke gets), in world px (the endless canvas: anywhere, the frame at home or not, negative px too), so no pointer move
waits for the scene to be described and drawn again. Only the stroke's own box is ever held, never the composition.

Two parts. The tip, the newest points, is stamped on the screen's thread at each look: a few points, cheap. The dry
part is the whole stroke so far stamped again as the saved stroke will be (a brush's dabs depend on the whole
stroke: its noise and tapers are sized by its length), so the tip never leaves a seam. That costs the whole stroke,
so it runs on a worker thread (`_DRY`): once the tip is CHUNK points long the next restamp starts, and the screen
takes it in at the first look after it is done (`settle`). The pen never waits for it.

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
        self._base = under                                              # what the stroke starts on (None: nothing)
        self._dry = under.copy() if under is not None else None        # a smear's paint so far (its tip smears it)
        self._settled, self._dry_box, self._dry_pic = 0, None, None     # points in the dry part; its box; its picture
        self._job, self._done = None, done                              # the restamp running; called when it is done

    @property
    def ready(self) -> bool:
        """Whether there is anything to show yet (an eraser waits for the frame without its layer)."""
        return not self.erasing or self.reveal is not None

    def reveal_with(self, frame: np.ndarray, origin: tuple[int, int]):
        self.reveal, self._origin = frame, origin

    def add(self, x: float, y: float, pressure: float):
        self.points.append([x, y, round(min(max(pressure, 0.0), 1.0), 3)])

    def _box(self, pts) -> tuple[int, int, int, int] | None:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x0, y0 = math.floor(min(xs) - self.reach), math.floor(min(ys) - self.reach)
        x1, y1 = math.ceil(max(xs) + self.reach), math.ceil(max(ys) + self.reach)
        if self.bounds is not None:                                     # a smear stays on its canvas
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(self.bounds[0], x1), min(self.bounds[1], y1)
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    def _tip(self) -> list:
        return self.points[max(0, self._settled - 1):]

    def _stamp(self, into, origin, pts):
        item = build("stroke", self.sid, {**self.brush, "size": self.size, "seed": seed_of(self.sid),
                                          "points": [[x - origin[0], y - origin[1], p] for x, y, p in pts]})
        canvas.stamp(into, item, into.shape[1], into.shape[0], {}, into[..., :3].copy() if item["smudge"] else None)

    def _restamp(self, pts, box, base):
        """(worker thread) The whole stroke `pts` stamped again into its box, on what it starts on, and its picture."""
        x0, y0, x1, y1 = box
        part = base if base is not None else np.zeros((y1 - y0, x1 - x0, 4), np.float32)
        self._stamp(part, (x0, y0), pts)
        return part, self._placed(*self._picture(part, (0, 0, x1 - x0, y1 - y0), (x0, y0)))

    def settle(self) -> bool:
        """Takes in a finished restamp of the dry part (True: it changed), and starts the next one once the tip is
        CHUNK points long. A restamp that failed raises here, on the screen's thread."""
        changed = False
        if self._job is not None and self._job[0].done():
            future, box, n = self._job
            self._job = None
            x0, y0, x1, y1 = box
            part, self._dry_pic = future.result()
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
        w, h = x1 - x0, y1 - y0
        ax, ay = at or (x0, y0)
        if self.erasing:
            u8 = self._revealed(ax, ay, w, h)
            u8[..., 3] = np.minimum(u8[..., 3], np.clip(px[y0:y1, x0:x1, 3] * 255 + 0.5, 0, 255).astype(np.uint8))
        else:
            u8 = np.ascontiguousarray(compose.straight8(px[y0:y1, x0:x1]))
        return QImage(u8.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy(), {"x": ax, "y": ay, "w": w, "h": h}

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
