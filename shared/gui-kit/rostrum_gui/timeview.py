"""A timeline's view: which stretch of time is on screen (INTERACTION.md 1.6 › Zoom and scroll, 1.12). The one source
of truth for time → x: the ruler, rows, markers, playhead and a piano roll's time axis all draw `start` .. `start +
span` across their own width. It is screen state, never part of the document: zooming is not an edit, there is no
undo step, and an agent never moves it.

    v = TimeView(20.0)                 # 20 s long; "fit" (the default) shows it all and follows its length
    v.zoom(2, 0.75)                    # zoom in around the moment 3/4 across the width (the pointer)
    v.x_of(t, width) / v.t_of(x, width)  # seconds <-> pixels for a strip `width` px wide
    v.follow(playhead)                 # while playing: turn the page when the playhead leaves the view
    TimeViewObject(v)                  # the same view for QML: start / span / fit / length, the slots below

Zooming in leaves fit; zooming back out to the whole length returns to it. `auto` is a view the screen chose (fit to a
track's notes); a person's first zoom or scroll clears it. Bad input (a length or factor that is not a positive number)
is refused loudly with a ValueError. Moved from Sound's screensound/view.py (S35).
"""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QObject, Signal, Slot

MARGIN = 0.15            # of a stretch's length, left empty each side by fit_to
MIN_SPAN = 0.5           # seconds: the closest zoom
STEP = 1.25              # one key press / wheel notch
WHEEL_SCROLL = 0.1       # a wheel notch scrolls this much of the view
PAGE_LEAD = 0.1          # after a page turn the playhead sits this far in from the left


def _num(name, v, positive=False):
    v = float(v)
    if not math.isfinite(v) or (positive and v <= 0) or v < 0:
        raise ValueError(f"time view: {name} must be a {'positive' if positive else 'non-negative'} number, not {v!r}")
    return v


class TimeView:
    def __init__(self, length: float = 1.0):
        self.start, self._span, self.fit, self.auto = 0.0, 1.0, True, False
        self.length = _num("length", length, positive=True)

    @property
    def span(self) -> float:
        """How many seconds the view shows across its width."""
        n = self.length
        return n if self.fit else min(max(self._span, min(MIN_SPAN, n)), n)

    def set_length(self, length: float):
        """The timeline got longer or shorter (an edit): keep the view inside it."""
        self.length = _num("length", length, positive=True)
        self.clamp()

    def clamp(self):
        if self.fit or self.span >= self.length - 1e-6:
            self.start, self.fit = 0.0, True
        else:
            self.start = min(max(self.start, 0.0), self.length - self.span)

    def x_of(self, t: float, width: float) -> float:
        return (t - self.start) * width / self.span

    def t_of(self, x: float, width: float) -> float:
        return self.start + x * self.span / _num("width", width, positive=True)

    def zoom(self, factor: float, frac: float = 0.5):
        """Zoom in by `factor` (> 1; < 1 zooms out) keeping the moment at `frac` (0 left .. 1 right) in place."""
        factor, n, span = _num("zoom factor", factor, positive=True), self.length, self.span
        frac = min(max(float(frac), 0.0), 1.0)
        self.auto = False
        t = self.start + frac * span
        new = min(max(span / factor, min(MIN_SPAN, n)), n)
        self._span, self.fit = new, new >= n - 1e-6
        self.start = t - frac * new
        self.clamp()

    def zoom_step(self, factor: float, playhead: float):
        """A key's zoom (Ctrl+= / Ctrl+-): around the playhead when it is on screen, else the middle."""
        frac = (playhead - self.start) / self.span
        self.zoom(factor, frac if 0 <= frac <= 1 else 0.5)

    def scroll(self, dt: float):
        if not self.fit:
            self.auto = False
            self.start += float(dt)
            self.clamp()

    def set_start(self, t: float):
        self.scroll(float(t) - self.start)

    def show_all(self):
        """Ctrl+0: fit everything."""
        self.start, self.fit, self.auto = 0.0, True, False

    def fit_to(self, a: float, b: float, chosen: bool = False):
        """F: show a .. b with some margin round it (the whole length when that is nearly all of it). `chosen`: the
        screen picked it, not a person (`auto`)."""
        a, b = sorted((float(a), float(b)))
        pad = max((b - a) * MARGIN, MIN_SPAN)
        a, b = max(a - pad, 0.0), min(b + pad, self.length)
        if b - a >= self.length * 0.9:
            return self.show_all()
        self._span, self.fit, self.auto, self.start = max(b - a, min(MIN_SPAN, self.length)), False, chosen, a
        self.clamp()

    def wheel(self, dx: float, dy: float, ctrl: bool, shift: bool, frac: float, vertical: bool) -> bool:
        """A wheel turn over a timeline (120 = one notch). Ctrl: zoom around the pointer (`frac` across the width).
        Shift or a sideways swipe: scroll in time. A plain turn scrolls in time only when the caller has nothing to
        scroll up and down (`vertical` false). False: the caller should scroll its rows instead."""
        if ctrl:
            self.zoom(STEP ** (dy / 120.0), frac)
        elif dx or shift or not vertical:
            self.scroll(-(dx or dy) / 120.0 * self.span * WHEEL_SCROLL)
        else:
            return False
        return True

    def follow(self, t: float) -> bool:
        """Page-follow while playing: when the playhead leaves the view, turn the page so it sits near the left.
        True when the view moved."""
        span = self.span
        if self.fit or self.start <= t <= self.start + span:
            return False
        self.start = t - PAGE_LEAD * span
        self.clamp()
        return True


class TimeViewObject(QObject):
    """A TimeView for QML. Bind to start / span (every strip computes x = (t - start) * width / span, so its
    bindings follow the view); call the slots for what a person does. Each change emits `changed` once."""
    changed = Signal()

    def __init__(self, view: TimeView | None = None, parent=None):
        super().__init__(parent)
        self.view = view or TimeView()

    def _do(self, fn, *a):
        out = fn(*a)
        self.changed.emit()
        return out

    start = Property(float, lambda s: s.view.start, notify=changed)
    span = Property(float, lambda s: s.view.span, notify=changed)
    fit = Property(bool, lambda s: s.view.fit, notify=changed)
    length = Property(float, lambda s: s.view.length, notify=changed)

    @Slot(float)
    def setLength(self, n):
        self._do(self.view.set_length, n)

    @Slot(float, float)
    def zoomAt(self, factor, frac):
        self._do(self.view.zoom, factor, frac)

    @Slot(float, float)
    def zoomStep(self, factor, playhead):
        self._do(self.view.zoom_step, factor, playhead)

    @Slot(float)
    def scrollBy(self, dt):
        self._do(self.view.scroll, dt)

    @Slot(float)
    def setStart(self, t):
        self._do(self.view.set_start, t)

    @Slot()
    def showAll(self):
        self._do(self.view.show_all)

    @Slot(float, float)
    def fitTo(self, a, b):
        self._do(self.view.fit_to, a, b)

    @Slot(float, float, bool, bool, float, bool, result=bool)
    def wheel(self, dx, dy, ctrl, shift, frac, vertical):
        return self._do(self.view.wheel, dx, dy, ctrl, shift, frac, vertical)

    @Slot(float, result=bool)
    def follow(self, t):
        moved = self.view.follow(t)
        if moved:
            self.changed.emit()
        return moved
