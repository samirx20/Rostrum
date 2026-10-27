"""Coverage while painting (brief 21a), for QML as `paintMode.coverage`: the Paint layers header reads "Seen by Hero 01:
62 % painted" (how much of what the shot's camera sees of the item is painted) and its toggle shows the coverage tint,
a faint orange hatch on the surface where the shot sees it and nothing is painted yet (rostrum3d.coverage). Both come
from the shot camera's texel picture, the same one painting from the view uses (texels.py).

After each change while Paint is on, the engine's worker measures the scene the viewport is drawing (its `sent()`
scene, so nothing is loaded twice); with the tint on, that scene is swapped for its tinted copy and drawn again. The
tint is screen state only: never in Final, a render or an export (they compile their own scene).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

WIDTH = 960                      # the texel picture's width for coverage (the shot's shape)


class Coverage(QObject):
    changed = Signal()
    measured = Signal(object)        # (scene measured, {item: percent}, tinted scene, seen ids) from the worker

    def __init__(self, paint, viewport):
        super().__init__(paint)
        self.p, self.v, self.b = paint, viewport, paint.b
        self._on, self._percent, self._seen, self._busy, self._again = False, None, set(), False, False
        self._tinted = None                      # the tinted scene the viewport draws now (never measured again)
        self._timer = QTimer(self, singleShot=True, interval=150)          # after a change settles
        self._timer.timeout.connect(self._measure)
        self.measured.connect(self._on_measured)
        self.b.docChanged.connect(self.later)
        paint.changed.connect(self.later)

    on = Property(bool, lambda s: s._on, notify=changed)                   # the tint shows
    line = Property(str, lambda s: s._line(), notify=changed)

    def _line(self) -> str:
        it = self.p._item()
        if not self.p._on or it is None:
            return ""
        name = self._shot_name()
        if self._percent is None:
            return ""
        if it["id"] not in self._seen:
            return f"Not seen by {name}"
        return f"Seen by {name}: {self._percent.get(it['id'], 0.0):.0f} % painted"

    def _shot_name(self) -> str:
        sid = self.b.shot_id
        return next((s.get("name") or s["id"] for s in self.b.doc.data.get("shots", []) if s["id"] == sid), sid)

    @Slot()
    def toggle(self):
        self._on = not self._on
        self.changed.emit()
        self.v._on_doc()                         # the plain scene again (tint off), or measured and tinted (on)
        self.later()

    def later(self, *_):
        if self.p._on:
            self._timer.start()

    def _measure(self):
        if not self.p._on or self.v._size is None:
            return
        if self._busy:
            self._again = True
            return
        info = self.b.shot_info()
        if not info.get("camera") or not info.get("width"):
            return
        scene = self.v.sent()[0]
        if scene is self._tinted:                # already measured and tinted: nothing changed since
            return
        data, frame = self.b.doc.data, self.b.frame
        h = max(16, round(WIDTH * info["height"] / info["width"]))
        req = {"camera": info["camera"], "frame": frame, "width": WIDTH, "height": h}
        self._busy = True

        def job(eng):
            from rostrum3d import coverage, paint_scene, texels
            try:
                eng.ensure_scene(scene)
                done = scene                      # paint still waiting for its picture (a new view, a new clay): laid here
                if scene.get(paint_scene.LATER):
                    first = {k: v for k, v in scene.items() if k != paint_scene.LATER}
                    done = paint_scene.finish(first, scene[paint_scene.LATER], eng.texels_reply)
                percent, tinted = coverage.for_screen(done, data, req, eng.texels_reply)
                pic = texels.cached(paint_scene.geometry_scene(done), req)
                seen = {i for i in (pic.items if pic is not None else []) if pic.of(i).any()}
                self.measured.emit((scene, percent, tinted, seen))
            except Exception as e:  # noqa: BLE001  said on the status line, never a silent miss
                self.measured.emit((scene, str(e), None, set()))
        self.v._r.call(job)

    def _on_measured(self, answer):
        self._busy = False
        scene, percent, tinted, seen = answer
        if isinstance(percent, str):
            self.b.fail_line(f"Error: coverage: {percent}")
        else:
            self._percent, self._seen = percent, seen
            self.changed.emit()
            if self._on and tinted is not None and not self.v.final.on and self.v.swap_scene(scene, tinted):
                self._tinted = tinted
                self.v.redraw()
        if self._again:
            self._again = False
            self._timer.start()
