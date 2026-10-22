"""The timeline's view: which stretch of the song is on screen (no Qt). One source of truth for time → x:
the ruler, markers, rows, playhead and the piano roll's time axis all draw `start` .. `start + span` across
their own width. It is screen state, not part of the document (zooming is not an edit).

"Fit" (the default) shows the whole song and follows its length; zooming in leaves fit, zooming back out to the
whole song returns to it. `auto` is a view the screen chose (fit to a track's notes); the first zoom or scroll
by a person clears it, and until then the screen may choose again for the next track.
"""
from __future__ import annotations

MARGIN = 0.15            # of the notes' length, left empty each side by fit_to
MIN_SPAN = 0.5            # seconds: the closest zoom
STEP = 1.25               # one key press / wheel notch


class View:
    def __init__(self):
        self.start, self._span, self.fit, self.auto = 0.0, 1.0, True, False

    def span(self, length: float) -> float:
        return length if self.fit else min(max(self._span, min(MIN_SPAN, length)), length)

    def clamp(self, length: float):
        """Keep the view inside the song (its length may change under an edit)."""
        if self.fit or self.span(length) >= length - 1e-6:
            self.start, self.fit = 0.0, True
        else:
            self.start = min(max(self.start, 0.0), length - self.span(length))

    def zoom(self, factor: float, frac: float, length: float):
        """Zoom in by `factor` (> 1; < 1 zooms out) keeping the moment at `frac` (0 left .. 1 right) in place."""
        span = self.span(length)
        self.auto = False
        t = self.start + min(max(frac, 0.0), 1.0) * span
        new = min(max(span / factor, min(MIN_SPAN, length)), length)
        self._span, self.fit = new, new >= length - 1e-6
        self.start = t - frac * new
        self.clamp(length)

    def scroll(self, dt: float, length: float):
        if not self.fit:
            self.auto = False
            self.start += dt
            self.clamp(length)

    def set_start(self, t: float, length: float):
        self.scroll(t - self.start, length)

    def show_all(self):
        self.start, self.fit, self.auto = 0.0, True, False

    def fit_to(self, a: float, b: float, length: float):
        """Show the stretch a .. b with some margin round it (the whole song when that is nearly all of it)."""
        pad = max((b - a) * MARGIN, MIN_SPAN)
        a, b = max(a - pad, 0.0), min(b + pad, length)
        if b - a >= length * 0.9:
            return self.show_all()
        self._span, self.fit, self.auto, self.start = max(b - a, min(MIN_SPAN, length)), False, True, a
        self.clamp(length)

    def follow(self, t: float, length: float) -> bool:
        """Page-follow while playing: when the playhead leaves the view, turn the page so it sits near the left.
        True when the view moved."""
        span = self.span(length)
        if self.fit or self.start <= t <= self.start + span:
            return False
        self.start = t - 0.1 * span
        self.clamp(length)
        return True
