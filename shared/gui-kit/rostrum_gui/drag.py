"""Drag feel, the ONE state machine for every app (INTERACTION.md 1.10): a press becomes a drag only after the pointer
moves 4 px (less is a click); Ctrl / Alt / Shift mean the same everywhere; Esc puts everything back; and the small
label by the pointer says the value. The document side is edits.Drag / Scrub (one press-drag-release = one change,
cancel = none); this only decides when to open it and when to end or cancel it.

    d = PointerDrag(x, y, lambda: Drag(doc, who, "Move logo"))   # at the press; nothing is opened yet
    if d.move(x, y): d.preview(calls)                            # each pointer move; True once it is a drag
    d.cancel()                                                    # Esc: the document is as before, no undo step
    change = d.release()                                          # one change (None: a click, a cancel, no edit)

`Mods.of(event.modifiers)` reads the keys on every move: Ctrl = no snapping (`free`), Alt = drag a copy (`copy`, from
the centre on a resize handle), Shift = keep it straight (`straight`: one axis, proportions, 15° turns, only in time).
`DragView` holds what QML shows while a drag runs: the label (DragLabel.qml) and the caught line (SnapLine.qml).
Screen state only, cleared when the drag ends. Esc during a drag cancels it in one place for every app (drag_esc.py:
the press holds the window's Esc once it is a drag); `grabbed(x0, y0)` keeps the point grabbed under the pointer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import Property, QObject, Qt, Signal

from .drag_esc import ESC

THRESHOLD = 4.0           # screen px: a press that moves less is a click, never a drag (1.10)
TURN_STEP = 15.0          # degrees: Shift on a turn


@dataclass(frozen=True)
class Mods:
    free: bool = False        # Ctrl: no snapping for this move
    copy: bool = False        # Alt: drag a copy
    straight: bool = False    # Shift: keep it straight

    @classmethod
    def of(cls, flags) -> "Mods":
        """From Qt keyboard modifiers (an event's `modifiers`, as a flag or an int from QML)."""
        f = int(getattr(flags, "value", flags))
        on = lambda m: bool(f & m.value)                                      # noqa: E731
        return cls(on(Qt.ControlModifier), on(Qt.AltModifier), on(Qt.ShiftModifier))


def straight(dx: float, dy: float) -> tuple[float, float]:
    """Shift on a move: only along the axis it has moved most."""
    return (dx, 0.0) if abs(dx) >= abs(dy) else (0.0, dy)


def turn_steps(degrees: float) -> float:
    """Shift on a turn: the nearest 15° step."""
    return round(degrees / TURN_STEP) * TURN_STEP


class PointerDrag:
    """One press, from press to release. `open()` makes the document drag (an edits.Drag or Scrub); it is called once,
    when the press first moves 4 px, so a click never opens a gesture and never records anything."""

    def __init__(self, x: float, y: float, open):
        self.x0, self.y0, self.x, self.y = float(x), float(y), float(x), float(y)
        self._open, self._drag, self.state = open, None, "pressed"   # pressed | dragging | cancelled | done
        self.mods = Mods()

    @property
    def dx(self) -> float:
        return self.x - self.x0

    @property
    def dy(self) -> float:
        return self.y - self.y0

    @property
    def dragging(self) -> bool:
        return self.state == "dragging"

    def move(self, x: float, y: float, mods: Mods | None = None) -> bool:
        """The pointer moved (screen px). True while this press is a drag: the caller then previews the move."""
        if self.state in ("cancelled", "done"):
            return False
        self.x, self.y, self.mods = float(x), float(y), mods or self.mods
        if self.state == "pressed" and math.hypot(self.dx, self.dy) >= THRESHOLD:
            self._drag, self.state = self._open(), "dragging"
            ESC.hold(self.cancel)               # Esc now cancels this drag, before anything else hears it (drag_esc.py)
        return self.state == "dragging"

    def preview(self, calls):
        """Show this move's calls on the document (live, not yet a change). Only while dragging."""
        if self.state != "dragging":
            raise RuntimeError(f"drag: can't preview while the press is {self.state} (not a drag)")
        self._drag.preview(calls)

    def cancel(self) -> None:
        """Esc during the drag: everything goes back, nothing is recorded. The release that follows does nothing."""
        ESC.let_go(self.cancel)
        if self.state == "dragging":
            self._drag.end(cancel=True)
        if self.state in ("pressed", "dragging"):
            self.state = "cancelled"

    def release(self):
        """The press ends: the drag's one change (None for a click, a cancelled drag, or a drag that changed
        nothing). `clicked` says it was a click."""
        was, self.state = self.state, "done"
        ESC.let_go(self.cancel)
        return self._drag.end() if was == "dragging" else None

    def grabbed(self, x: float, y: float):
        """Where the dragged thing goes now, given where it was at the press (`x`, `y`): the pointer's move, so the
        point grabbed stays under the pointer (no jump on the press; 1.22 canvas rule 4)."""
        return x + self.dx, y + self.dy

    @property
    def clicked(self) -> bool:
        return self._drag is None and self.state == "done"


# ---- the label's words (the value, never a name for it) -------------------------------------------------------
def _n(v: float, places: int = 0) -> str:
    s = f"{v:.{places}f}"
    return s.replace("-", "−") if v < 0 and float(s) != 0 else s.lstrip("-")


def words_xy(x: float, y: float) -> str:
    return f"X {_n(x)}  Y {_n(y)}"


def words_size(w: float, h: float) -> str:
    return f"{_n(w)} × {_n(h)}"


def words_angle(degrees: float) -> str:
    return f"{_n(degrees, 1 if degrees != round(degrees) else 0)}°"


def words_span(start: float, end: float) -> str:
    return f"{_n(start, 2)} s → {_n(end, 2)} s"


def words_beats(beats: float, per_bar: int = 4, signed: bool = True) -> str:
    """A length or a move in musical time for the value chip: "+1 bar 2 beats", "−3 beats", "+½ beat", "2 bars"."""
    sign = "−" if beats < 0 else "+" if signed and beats > 0 else ""
    b = abs(beats)
    bars, rest = divmod(round(b * 4) / 4, per_bar)
    frac = {0.25: "¼", 0.5: "½", 0.75: "¾"}
    whole, part = int(rest), rest - int(rest)
    beat_words = (f"{whole or ''}{frac[part]}" if part else f"{whole}") if rest else ""
    out = [f"{int(bars)} bar{'s' if bars != 1 else ''}"] if bars else []
    if beat_words:
        out.append(f"{beat_words} beat{'s' if rest > 1 else ''}")
    return sign + (" ".join(out) or "0 beats")


def words_db(db: float) -> str:
    return f"{_n(db, 1)} dB"


HINTS = {"move": {"straight": "straight line", "copy": "copy", "free": "no snapping"},
         "resize": {"straight": "keep ratio", "copy": "from centre", "free": "no snapping"},
         "turn": {"straight": f"{TURN_STEP:g}° steps", "free": "no snapping"},
         "time": {"straight": "only in time", "copy": "copy", "free": "no snapping"}}


def hint_of(mods: Mods, kind: str = "move") -> str:
    """The chip's second words: what the keys held mean for this drag ("keep ratio · from centre"); "" with none."""
    said = HINTS[kind]
    return " · ".join(said[k] for k in ("straight", "copy", "free") if getattr(mods, k) and k in said)


class DragView(QObject):
    """What a running drag shows: `text` by the pointer at (`x`, `y`, the view's px), and the caught line: `caught`,
    `lineAt` (px across the view: an x for a `vertical` line, else a y) and `lineName` ("drop")."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._s = ("", 0.0, 0.0, None, "", True, "")

    text = Property(str, lambda self: self._s[0], notify=changed)
    x = Property(float, lambda self: self._s[1], notify=changed)
    y = Property(float, lambda self: self._s[2], notify=changed)
    caught = Property(bool, lambda self: self._s[3] is not None, notify=changed)
    lineAt = Property(float, lambda self: self._s[3] or 0.0, notify=changed)
    lineName = Property(str, lambda self: self._s[4], notify=changed)
    vertical = Property(bool, lambda self: self._s[5], notify=changed)
    hint = Property(str, lambda self: self._s[6], notify=changed)     # what a held key does now ("15° steps", "keep ratio")

    def show(self, text: str, x: float, y: float, line_at: float | None = None, line_name: str = "",
             vertical: bool = True, hint: str = ""):
        """A drag moved: the chip's words and place (the pointer); the caught line's place and name (None: nothing
        caught); `hint`: what a held key does now (`hint_of(mods, kind)`)."""
        self._set((text, float(x), float(y), None if line_at is None else float(line_at), line_name, bool(vertical),
                   hint))

    def clear(self):
        self._set(("", 0.0, 0.0, None, "", True, ""))

    def _set(self, s):
        if s != self._s:
            self._s = s
            self.changed.emit()
