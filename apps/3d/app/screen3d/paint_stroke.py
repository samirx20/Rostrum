"""Paint mode's stroke (paint_mode_qt.py's PaintMode): a left drag on the viewport, picked point by point by the engine
(its `uv` on a mesh; on a clay its `local` point and normal, kept as the stroke's anchors on the surface), drawn as a
trail over the picture while the drag lasts; the release is one call list, one undo step (paint_mode.stroke_calls).
A clay stroke's reach (brush radius in metres) is the brush size × the surface's metres per canvas px where it
landed (paint_mode.clay_reach). One pick at a time: while the engine answers, only the newest position waits, so it
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
        self._anchors, self._moved, self._mpp = [], [0.0, 0.0], None      # a clay's: anchors, 3D / screen run, m per px
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
        elif r.get("hit") and r.get("item") == self._id and (self._item() or {}).get("type") == "clay":
            self._on_clay(r, x, y)
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

    def _on_clay(self, r, x, y):
        """One pick on the clay: an anchor (its point and normal in the clay's own space), and the brush's scale."""
        if not r.get("local") or not r.get("localNormal"):
            self._up = True
            return self.b.fail_line("Error: paint: the engine's pick gave no point on the clay's surface (`local`); "
                                    "the 3D core is older than this app: build it again")
        a = [*(round(v, 6) for v in r["local"]), *(round(v, 5) for v in r["localNormal"]), 1.0]
        if r.get("rest"):                   # a posed clay: the stroke is kept on the rest shape, as sculpting is
            normal = P.clay_rest_normal(self._scene, self._id, r["rest"], a[3:6])
            a = [*(round(v, 6) for v in r["rest"]), *(round(v, 5) for v in normal), 1.0]
        if self._anchors:
            self._moved[0] += sum((p - q) ** 2 for p, q in zip(a[:3], self._anchors[-1][:3])) ** 0.5
            self._moved[1] += ((x - self._last[0]) ** 2 + (y - self._last[1]) ** 2) ** 0.5
        if self._mpp is None:
            self._mpp = P.clay_mpp(self._scene, self._id, a) or 0.0
        if self._mpp and self._moved[0] > 0:            # screen px per canvas px: the cursor's size
            self._ratio = max(0.05, min(20.0, self._mpp * self._moved[1] / self._moved[0]))
        self._anchors.append(a)
        self._last = (x, y)

    def _finish(self):
        pts, self._pts, self._scene = self._pts, [], None
        anchors, self._anchors = self._anchors, []
        self._trail = []
        self.trailChanged.emit()
        it = self._item()
        clay = it is not None and it.get("type") == "clay"
        if clay and self._moved[0] > 0:
            self._mpp_screen = self._moved[0] / max(self._moved[1], 1e-9)    # kept for a later click
        if it is None or not (anchors if clay else pts):
            return self.b.say(f"Paint lands on {self._name()} only: start the stroke on it." if it else "")
        layer, new = self._active, None
        if self._layer() is None:                 # no layer yet: the stroke makes one (same undo step)
            new = {**P.new_layer_args(it, "colour"), "id": next(f"paint_{n}" for n in range(1, 10**6)
                                                               if not self.b.doc.has(f"paint_{n}"))}
            layer = new["id"]
        brush = dict(self.brush.values)
        reach = P.clay_reach(brush.get("size", 24.0), self._mpp, self._mpp_screen) if clay else 0.0
        calls = P.stroke_calls(it, layer, pts, brush, new, anchors, reach)
        if self.b._guard(lambda: self.b._apply(calls, f"Paint on {self._name()}")):
            self._active = layer
            self.changed.emit()
