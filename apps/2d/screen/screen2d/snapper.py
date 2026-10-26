"""Snapping during a canvas drag, as QML sees it (backend.snap): what the dragged layers may catch, the offset, and the
magenta lines of what they caught (`lines`, composition px; Stage.qml draws them through its mapping, SnapLine.qml the
equal-gap brackets and gap numbers among them). The maths is snap.py; the boxes are bounds.boxes (the screen's one
source of where layers are). A layer's move also snaps to equal gaps (snap.spacing, worked out once at the press).

A drag calls begin(layers) at the press, move(dx, dy) / edge(hx, hy, dx, dy) on every pointer move (the total drag,
composition px; it returns the drag to use) and end() on release. QML reports the keys with keys(free, straight):
free = Ctrl pressed after the drag started (no snapping for this drag), straight = Shift (keep to the main axis).
The snap distance is 6 screen px at the view's zoom (bridge.view_zoom(): screen state, shown.py).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from rostrum2d.frame import view as camera

from . import bounds, snap as S


class Snapper(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._lines, self._on = bridge, [], True
        self._start, self._targets, self._free, self._straight = None, [], False, False
        self._spaced = None                     # equal gaps among the targets (snap.spacing): a layer's move only

    @Property("QVariantList", notify=changed)
    def lines(self):
        return self._lines

    @Property(bool, notify=changed)
    def on(self):
        """The Snap switch (view controls): on by default; off = no drag snaps."""
        return self._on

    @Slot(bool)
    def setOn(self, on):
        self._on = bool(on)
        self.changed.emit()

    @Slot(bool, bool)
    def keys(self, free, straight):
        self._free, self._straight = bool(free), bool(straight)

    def begin(self, layers, point=None) -> None:
        """The press: the moving layers' joint extent and what they may catch (the frame first, then the same
        group's visible layers, then the others; never the moving layers, their groups or what is inside them).
        `point` (x, y): a motion-path key square instead of a box: it is a box of no size there, and `layers` (its
        layer) only says what not to catch."""
        boxes = bounds.boxes(self.b.placed(), self.b._t)
        moving = set(layers)
        mine = [b for b in boxes if b["id"] in moving]
        self._free = self._straight = False
        if point is not None:
            self._start = (point[0], point[1], point[0], point[1])
        elif not mine:
            self._start = None
            return
        else:
            es = [bounds.extent(b) for b in mine]
            self._start = (min(e[0] for e in es), min(e[1] for e in es), max(e[2] for e in es), max(e[3] for e in es))
        mine = mine or [{"up": ()}]
        ups = {g for b in mine for g in b["up"]}
        home = mine[0]["up"][-1:] if mine[0]["up"] else ()
        c = self.b.comp()
        self._targets = [S.frame_target(c["width"], c["height"], camera.shot(self.b.placed(), self.b._t))]
        for b in boxes:
            if b["id"] in moving or b["id"] in ups or moving & set(b["up"]) or b["w"] <= 0 or b["h"] <= 0 or b["opacity"] <= 0:
                continue
            self._targets.append((1 if b["up"][-1:] == tuple(home) else 2, bounds.extent(b)))
        self._spaced = S.spacing(self._targets) if point is None else None

    def begin_box(self, box, targets) -> None:
        """The press of a drag that isn't a layer's (the frame, frame_drag.py): its extent (x0, y0, x1, y1) and what it
        may catch, [(rank, extent)]."""
        self._free = self._straight = False
        self._start, self._targets, self._spaced = tuple(box), list(targets), None

    def _snap(self, box, xs, ys, spaced=None):
        if not self._on or self._free or self._start is None:
            self._set([])
            return 0.0, 0.0
        dx, dy, lines = S.snap(box, self._targets, S.threshold(self.b.view_zoom()), xs, ys, spaced)
        self._set(lines)
        return dx, dy

    def move(self, dx: float, dy: float) -> tuple[float, float]:
        """A move by (dx, dy) from the press: straightened (Shift) and snapped."""
        if self._straight:
            dx, dy = S.straight(dx, dy)
        if self._start is None:
            return dx, dy
        s, near = self._start, S.threshold(self.b.view_zoom())
        sx, sy = self._snap((s[0] + dx, s[1] + dy, s[2] + dx, s[3] + dy),      # an axis the pointer has hardly left stays put:
                            S.ALL if abs(dx) >= near else (), S.ALL if abs(dy) >= near else (), self._spaced)   # a straight pull down never leans
        return (dx + sx if sx else self._whole(dx)), (dy + sy if sy else self._whole(dy))

    def _whole(self, d: float) -> float:
        """A drag the snap didn't catch lands on whole pixels (finer when zoomed in), not on the fraction the pointer's screen
        pixel maps to: a row copied by dragging stays an exact step apart."""
        q = 1.0 / max(1, round(self.b.view_zoom()))
        return round(d / q) * q

    def edge(self, hx: int, hy: int, dx: float, dy: float) -> tuple[float, float]:
        """A resize handle (hx, hy) dragged by (dx, dy): the dragged edge(s) snap. Only for an unturned box (a turned
        box's edges aren't its extent's)."""
        if self._start is None:
            return dx, dy
        s = self._start
        box = (s[0] + (dx if hx < 0 else 0), s[1] + (dy if hy < 0 else 0), s[2] + (dx if hx > 0 else 0), s[3] + (dy if hy > 0 else 0))
        sx, sy = self._snap(box, () if not hx else (0,) if hx < 0 else (2,), () if not hy else (0,) if hy < 0 else (2,))
        return dx + sx, dy + sy

    def begin_edge(self, layer: str, turned: bool) -> None:
        self.begin([layer])
        if turned:
            self._start = None

    def end(self) -> None:
        self._start, self._targets, self._spaced = None, [], None
        self._set([])

    def _set(self, lines):
        if lines != self._lines:
            self._lines = lines
            self.changed.emit()
