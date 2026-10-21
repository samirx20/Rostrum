"""The timeline's view: which stretch of the song is on screen (no Qt). One source of truth for time → x:
the ruler, markers, rows, playhead and the piano roll's time axis all draw `start` .. `start + span` across
their own width. It is screen state, not part of the document (zooming is not an edit).

"Fit" (the default) shows the whole song and follows its length; zooming in leaves fit, zooming back out to the
whole song returns to it.
"""
from __future__ import annotations

MIN_SPAN = 0.5            # seconds: the closest zoom
STEP = 1.25               # one key press / wheel notch


class View:
    def __init__(self):
        self.start, self._span, self.fit = 0.0, 1.0, True

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
        t = self.start + min(max(frac, 0.0), 1.0) * span
        new = min(max(span / factor, min(MIN_SPAN, length)), length)
        self._span, self.fit = new, new >= length - 1e-6
        self.start = t - frac * new
        self.clamp(length)

    def scroll(self, dt: float, length: float):
        if not self.fit:
            self.start += dt
            self.clamp(length)

    def set_start(self, t: float, length: float):
        self.scroll(t - self.start, length)

    def show_all(self):
        self.start, self.fit = 0.0, True

    def follow(self, t: float, length: float) -> bool:
        """Page-follow while playing: when the playhead leaves the view, turn the page so it sits near the left.
        True when the view moved."""
        span = self.span(length)
        if self.fit or self.start <= t <= self.start + span:
            return False
        self.start = t - 0.1 * span
        self.clamp(length)
        return True
