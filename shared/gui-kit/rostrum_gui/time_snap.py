"""Snapping in time, the ONE rule for every app's timeline (2D UX_SPEC 6.2, INTERACTION 1.11): a key drag, a key
stretch and a bar drag ask `snap` where a time lands among the app's targets (2D: screen2d/time_snap.py targets;
3D: screen3d/timeline3d.py), strongest first: shared markers, the playhead, other bars' ends and keys, the music's bar
starts, then its beats; within the reach the drag passes (seconds; 0 = Ctrl held: free), else the nearest whole frame.
Each answer says what it caught, so a marker drop can tie and the drag label can name it ("+6 f · drop").

`TimeSnap` (backend.timeSnap) holds what a running time drag shows: the label beside the dragged edge or key (its
time and its row, qml/DragLabel.qml) and the time it caught (the timeline's line, qml/SnapLine.qml). Screen state only,
cleared when the drag ends.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Property, QObject, Signal

RANK = {"marker": 0, "playhead": 1, "edge": 2, "key": 2, "measure": 3, "beat": 4}   # INTERACTION 1.11; bars over beats (UX_SPEC 3.28)


@dataclass(frozen=True)
class Target:
    kind: str           # marker | playhead | edge (a layer bar's start / end) | key | measure (a music bar) | beat
    name: str           # what the label says ("drop", "playhead", "Title start", "key · Title", "bar 2", "beat 5")
    t: float            # composition seconds


def snap(t: float, found: list[Target], within: float, fps: float) -> tuple[float, Target | None]:
    """Where `t` (composition seconds) lands: on the strongest target within `within` seconds (nearest among equals),
    else on the nearest whole frame."""
    near = [g for g in found if abs(g.t - t) <= within] if within > 0 else []
    if near:
        best = min(near, key=lambda g: (RANK[g.kind], abs(g.t - t)))
        return best.t, best
    return round(t * fps) / fps, None


def label(dt: float, fps: float, caught: Target | None = None) -> str:
    """The pointer's label: the offset in whole frames ("+6 f", "−3 f", "0 f"), and what it caught."""
    n = round(dt * fps)
    words = f"+{n} f" if n > 0 else f"−{-n} f" if n < 0 else "0 f"
    return f"{words} · {caught.name}" if caught is not None else words


class TimeSnap(QObject):
    """A running time drag: the label's words, where it sits (the dragged thing's time and layer row), what it caught."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text, self._t, self._row, self._at = "", 0.0, "", None

    text = Property(str, lambda self: self._text, notify=changed)
    t = Property(float, lambda self: self._t, notify=changed)                          # the dragged edge / key, seconds
    row = Property(str, lambda self: self._row, notify=changed)                        # its layer (the label's row)
    caught = Property(bool, lambda self: self._at is not None, notify=changed)        # snapped now
    caughtT = Property(float, lambda self: self._at or 0.0, notify=changed)           # where (composition seconds)

    def show(self, dt: float, fps: float, caught: Target | None, t: float, row: str):
        """A time drag moved: `dt` seconds from where it began, the dragged thing now at `t` on layer `row`."""
        now = (label(dt, fps, caught), caught.t if caught is not None else None, t, row)
        if now != (self._text, self._at, self._t, self._row):
            self._text, self._at, self._t, self._row = now
            self.changed.emit()

    def clear(self):
        if self._text or self._at is not None:
            self._text, self._at = "", None
            self.changed.emit()
