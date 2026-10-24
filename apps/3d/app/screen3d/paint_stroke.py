"""Paint mode's stroke (paint_mode_qt.py's PaintMode): a left drag on the viewport, picked point by point by the engine
(its `uv` on the mesh), drawn as a trail over the picture while the drag lasts; the release is one call list, one undo
step (paint_mode.stroke_calls). One pick at a time: while the engine answers, only the newest position waits, so it
never falls behind the pointer. The whole drag uses the scene of its press, so the engine loads it once.
"""
from __future__ import annotations

from PySide6.QtCore import Slot

from . import paint_mode as P


class PaintStroke:
    # device pixels, as viewport.click
    @Slot(float, float)
    def press(self, x, y):
        if not self._on or self._item() is None or self.v._size is None:
            return
        self._drag += 1
        self._pts, self._trail, self._busy, self._next, self._up = [], [], False, None, False
        self._scene, self._cam = self.v.sent()        # one scene for the whole drag: the engine loads it once
        self._add(x, y)

    @Slot(float, float)
    def move(self, x, y):
        if self._up or self._scene is None:
            return
        self._add(x, y)

    @Slot()
    def release(self):
        self._up = True
        if not self._busy:
            self._finish()

    def _add(self, x, y):
        w, h = self.v._size
        self._trail.append([x * self.v._scale / w, y * self.v._scale / h])
        self.trailChanged.emit()
        if self._busy:
            self._next = (x, y)                       # only the newest waits: the engine never falls behind
        else:
            self._pick(x, y)

    def _pick(self, x, y):
        self._busy, drag, scene = True, self._drag, self._scene
        req = {**self._cam, "x": round(x * self.v._scale), "y": round(y * self.v._scale)}

        def job(eng):
            try:
                eng.ensure_scene(scene)
                self.answered.emit((drag, eng.pick(**req), x, y))
            except Exception as e:  # noqa: BLE001  said on the status line, never a silent miss
                self.answered.emit((drag, str(e), x, y))
        self.v._r.call(job)

    def _on_answer(self, answer):
        drag, r, x, y = answer
        if drag != self._drag:
            return
        self._busy = False
        if isinstance(r, str):
            self._up = True
            self.b.fail_line(f"Error: paint: {r}")
        elif r.get("hit") and r.get("item") == self._id and r.get("uv"):
            size = (self._item() or {}).get("paintSize", 2048)
            p = P.canvas_px(r["uv"], size)
            if self._pts and (d := ((p[0] - self._pts[-1][0]) ** 2 + (p[1] - self._pts[-1][1]) ** 2) ** 0.5) > 1:
                self._ratio = max(0.05, min(20.0, ((x - self._last[0]) ** 2 + (y - self._last[1]) ** 2) ** 0.5 / d))
            self._pts.append([*p, 1.0])
            self._last = (x, y)
        if self._next is not None and not self._up:
            nxt, self._next = self._next, None
            return self._pick(*nxt)
        if self._up:
            self._finish()

    def _finish(self):
        pts, self._pts, self._scene = self._pts, [], None
        self._trail = []
        self.trailChanged.emit()
        it = self._item()
        if it is None or not pts:
            return self.b.say(f"Paint lands on {self._name()} only: start the stroke on it." if it else "")
        layer, new = self._active, None
        if self._layer() is None:                 # no layer yet: the stroke makes one (same undo step)
            new = {**P.new_layer_args(it, "colour"), "id": next(f"paint_{n}" for n in range(1, 10**6)
                                                               if not self.b.doc.has(f"paint_{n}"))}
            layer = new["id"]
        calls = P.stroke_calls(it, layer, pts, dict(self.brush.values), new)
        if self.b._guard(lambda: self.b._apply(calls, f"Paint on {self._name()}")):
            self._active = layer
            self.changed.emit()
