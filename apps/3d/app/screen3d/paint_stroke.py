"""Paint mode's stroke (paint_mode_qt.py's PaintMode): a left drag on the viewport, picked point by point by the engine
(its `uv` on a mesh; on a clay its `local` point and normal, kept as the stroke's anchors on the surface), drawn as a
trail over the picture while the drag lasts; the release is one call list, one undo step (paint_mode.stroke_calls).
A clay stroke's reach (brush radius in metres) is the brush size × the surface's metres per canvas px where it
landed (paint_mode.clay_reach). One pick at a time: while the engine answers, only the newest position waits, so it
never falls behind the pointer. The whole drag uses the scene of its press, so the engine loads it once.

From the view (`_where == "view"`, brief 21b): a move only adds the point to the trail (no engine work while the pointer
moves); the release asks the engine once which items the path crosses (its `texels` picture of this view, kept in the
shared cache, so making the canvas reads the same one) and stores the stroke as drawn on each (paint_mode.view_calls).
The trail stays drawn, in the brush's colour and width, until the painted picture is on screen.

Stamp (on a Relief layer, `_stamping`): the press is the whole gesture: its one point (picked, or kept as drawn From
the view) becomes one paint.stamp at the release (paint_mode.stamp_calls / view_stamp_calls), one undo step; moves
change nothing. A Stamp on a mesh is always kept as clicked in the view (`_by_view`), so it stands upright as seen
(rostrum3d.stamp_turn); on a clay it is picked (`at` on the surface: upright is the clay's +Y there).
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
        if self._by_view():
            self._pose = self.v.drawn_pose()
        self._add(x, y)

    @Slot(float, float)
    def move(self, x, y):
        if self._up or self._scene is None or self._stamping():     # a stamp is where the press was
            return
        self._add(x, y)

    @Slot()
    def release(self):
        if self._up and self._scene is None and not self._busy and not self._pts:
            return                                    # a stroke Esc cancelled (cancel()): its release changes nothing
        self._up = True
        if self._by_view() and self._scene is not None:
            return self._finish_view()
        if not self._busy:
            self._finish()

    def _by_view(self) -> bool:
        """The press is kept as drawn on the view's picture: From the view, or a Stamp on a mesh."""
        return self._where == "view" or (self._stamping() and (self._item() or {}).get("type") == "mesh")

    @property
    def stroking(self) -> bool:
        """A drag is under way (pressed, not yet let go): what Esc cancels (esc3d.py)."""
        return self._on and not self._up and self._scene is not None

    def cancel(self):
        """Esc in the middle of a stroke: drop it (nothing painted, no history step); Paint stays on. Moves until the
        release are ignored, and an engine answer still on its way is dropped (a new drag number)."""
        self._drag += 1
        self._up, self._scene, self._busy, self._next = True, None, False, None
        self._pts, self._anchors = [], []
        self._clear_trail()

    def _finish_view(self):
        """(From the view) one texels request for the drawn path's view: the items it crosses, then one change."""
        pts, scene, drag, geo = self._pts, self._scene, self._drag, self.v._compiled()
        self._pts, self._scene, self._busy = [], None, True
        if not pts:
            return self._clear_trail()
        view = P.view_pose(**self._pose)
        req = {k: view[k] for k in ("eye", "target", "fov", "frame", "width", "height")}

        def job(eng):
            from rostrum3d import paint_scene, texels
            try:
                eng.ensure_scene(scene)
                # keyed as the canvas-making asks for it (the compiled scene's geometry), so the paint is laid at once
                pic = texels.cached(paint_scene.geometry_scene(geo), req, eng.texels_reply)
                h, w = pic.item.shape

                def at(x, y):
                    i = int(pic.item[min(h - 1, max(0, int(y))), min(w - 1, max(0, int(x)))])
                    return pic.items[i] if i >= 0 else ""
                self.answered.emit((drag, {"view": P.crossed(at, pts), "points": pts, "pose": view}, 0, 0))
            except Exception as e:  # noqa: BLE001  said on the status line, never a silent miss
                self.answered.emit((drag, str(e), 0, 0))
        self.v._r.call(job)

    def _land_view(self, r):
        self._busy = False
        it = self._item()
        items = [i for i in r["view"] if self.b.doc.has(i) and self.b.doc.item(i).get("type") in P.CANVASES]
        if it is None or not items:
            self._clear_trail()
            return self.b.say("Stamp: click on the model." if self._stamping()
                              else "From the view: the stroke crossed nothing paintable.")
        if self._stamping():
            if self._where != "view":                 # a Stamp on the mesh being painted only
                items = [i for i in items if i == self._id]
                if not items:
                    self._clear_trail()
                    return self.b.say(f"Paint lands on {self._name()} only: click on it.")
            calls = P.view_stamp_calls(items[:1], self._id, self._active, self.brush.stamp, self.brush.values["size"],
                                       {**r["pose"], "points": r["points"]})
            self._holding = True
            if not self.b._guard(lambda: self.b._apply(calls, f"Stamp {self.b.label_of(self.b.doc.item(items[0]))}")):
                self._clear_trail()
            return self.changed.emit()
        brush = dict(self.brush.values)
        channel = (self._layer() or {}).get("channel", "colour")
        calls = P.view_calls(self.b.doc, items, self._id, self._active if self._layer() else "", channel, brush,
                             {**r["pose"], "points": r["points"]})
        names = ", ".join(self.b.label_of(self.b.doc.item(i)) for i in items)
        self._holding = True                          # the trail stays until the painted picture is on screen
        ok = self.b._guard(lambda: self.b._apply(calls, f"Paint from the view on {names}"))
        if ok and not self._layer():
            mine = next((c for c in calls if c["op"] == "stroke.add" and c["target"][0] and
                         any(p["id"] == c["target"][0] for p in (self._item() or {}).get("paints", []))), None)
            self._active = mine["target"][0] if mine else self._active
        self.changed.emit()
        if not ok:
            self._clear_trail()

    def _clear_trail(self):
        self._holding = False
        self._trail = []
        self.trailChanged.emit()

    def picture_came(self, *_):
        """The viewport drew a picture: a trail held after a release goes now (its paint is in the picture)."""
        if self._holding and self._up:
            self._clear_trail()

    def _add(self, x, y):
        w, h = self.v._size
        self._trail.append([x * self.v._scale / w, y * self.v._scale / h])
        self.trailChanged.emit()
        if self._by_view():                     # kept as drawn: picture px of the view, pressure 1
            self._pts.append([round(x * self.v._scale, 2), round(y * self.v._scale, 2), 1.0])
            return
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
        if isinstance(r, dict) and "view" in r:
            return self._land_view(r)
        if isinstance(r, str) and self._by_view():
            self._busy = False
            self._clear_trail()
            return self.b.fail_line(f"Error: paint from the view: {r}")
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
        it = self._item()
        clay = it is not None and it.get("type") == "clay"
        if clay and self._moved[0] > 0:
            self._mpp_screen = self._moved[0] / max(self._moved[1], 1e-9)    # kept for a later click
        if it is None or not (anchors if clay else pts):
            self._clear_trail()
            return self.b.say(f"Paint lands on {self._name()} only: start the stroke on it." if it else "")
        if self._stamping():                      # one whole picture where the press was
            reach = P.clay_reach(self.brush.values["size"], self._mpp, self._mpp_screen) if clay else 0.0
            calls = P.stamp_calls(it, self._active, self.brush.stamp, anchors, reach)
            self._holding = True
            if not self.b._guard(lambda: self.b._apply(calls, f"Stamp on {self._name()}")):
                self._clear_trail()
            return self.changed.emit()
        layer, new = self._active, None
        if self._layer() is None:                 # no layer yet: the stroke makes one (same undo step)
            new = {**P.new_layer_args(it, "colour"), "id": next(f"paint_{n}" for n in range(1, 10**6)
                                                               if not self.b.doc.has(f"paint_{n}"))}
            layer = new["id"]
        brush = dict(self.brush.values)
        reach = P.clay_reach(brush.get("size", 24.0), self._mpp, self._mpp_screen) if clay else 0.0
        calls = P.stroke_calls(it, layer, pts, brush, new, anchors, reach)
        self._holding = True                          # the trail stays until the painted picture is on screen
        if self.b._guard(lambda: self.b._apply(calls, f"Paint on {self._name()}")):
            self._active = layer
            self.changed.emit()
        else:
            self._clear_trail()
