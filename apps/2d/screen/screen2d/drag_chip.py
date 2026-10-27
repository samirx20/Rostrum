"""The value chip by the pointer while a canvas drag runs (INTERACTION 1.10, CANVAS idea 3): the kit's DragLabel in
Stage.qml, bound to `backend.dragChip` (a rostrum_gui.drag.DragView). Each canvas drag says its value here as it moves:
a move its offset ("+48, −12"), a resize the new size ("320 × 180"), a turn the angle ("35°"), the anchor its place
in the layer ("50 %, 50 %"), a shape handle its setting ("Radius 24"); with what a held key does under it ("15° steps").
Its place is the pointer's, in screen coordinates (QCursor.pos): Stage maps it into the canvas, so every drag (the
mouse's, a pen's) puts it by the pointer the same way. drags.endDrag / cancelDrag clear it (DragLabel lingers 600 ms).
Screen state only, never a document change.
"""
from __future__ import annotations

from PySide6.QtGui import QCursor
from rostrum_gui.drag import DragView, Mods, hint_of


def _n(v: float) -> str:
    s = f"{v:+.0f}"
    return "0" if s in ("+0", "-0") else s.replace("-", "−")


def words_offset(dx: float, dy: float) -> str:
    """A move's offset from where it began: "+48, −12"."""
    return f"{_n(dx)}, {_n(dy)}"


def view_of(bridge) -> DragView:
    """The bridge's one DragView (made on first use)."""
    v = getattr(bridge, "_drag_chip", None)
    if v is None:
        v = bridge._drag_chip = DragView()
    return v


def say(bridge, text: str, kind: str = "", shift=False, alt=False, ctrl=False) -> None:
    """The chip shows `text` by the pointer; `kind` ("move", "resize", "turn"): the held keys' words under it."""
    p = QCursor.pos()
    view_of(bridge).show(text, p.x(), p.y(), hint=hint_of(Mods(ctrl, alt, shift), kind) if kind else "")


def clear(bridge) -> None:
    view_of(bridge).clear()
