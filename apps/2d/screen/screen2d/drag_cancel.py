"""Esc during a drag puts everything back (CANVAS.md §3 rule 5): the picture and the history are exactly as at the press
(no undo step), and the drag's later moves and release do nothing. One place for every 2D drag, so a new one gets it too.

Every drag on the screen holds a `rostrum_gui.edits.Drag` in an `_drag` field of its owner (the bridge's own drags:
drags.cancelDrag; the pen's points, the curve editor, keys, bars, the rig, picked strokes, the panel's scrubs ...). Esc
(only while a mouse button is held) finds the owner whose drag is open and closes it with nothing: by the owner's own `cancelDrag()` when it has screen state
of its own to put back, else by dropping its `_drag` (and `_grab`) and ending the gesture cancelled. A paint stroke is
not cancelled: its wet ink is the stroke itself (one Ctrl+Z takes it). The key is caught before any shortcut, so Esc's
other jobs (close a panel, back to Select) wait until no drag is held.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QGuiApplication
from rostrum_gui.drag_esc import ESC
from rostrum_gui.edits import Drag

KEEP = ("painter",)                 # owners whose drag is a paint stroke (see above)


def _open(d) -> bool:
    """A pointer drag held open (a live popover box says how it ends, `interrupt`: its own Esc handles it)."""
    return isinstance(d, Drag) and not d.closed and d.interrupt is None


def _owners(b):
    """The bridge's parts that hold a drag (`_drag`), one level down too (the rig view holds its RigDrag)."""
    seen = set()
    for name, part in list(vars(b).items()):
        if name in KEEP or not isinstance(part, QObject) or id(part) in seen:
            continue
        seen.add(id(part))
        yield part
        inner = getattr(part, "_drag", None)
        if inner is not None and not isinstance(inner, (Drag, tuple)) and hasattr(inner, "_drag"):
            yield inner


def cancel(b) -> bool:
    """Close the open drag with nothing. False: no drag was open (Esc does its other jobs)."""
    if b.cancelDrag():
        return True
    if getattr(b, "_kit", None) is not None and b._kit.scrub is not None:     # a panel number or gradient handle scrub
        b.cancelScrub()
        return True
    for part in _owners(b):
        if not _open(getattr(part, "_drag", None)):
            continue
        if hasattr(part, "cancelDrag"):
            part.cancelDrag()
            return True
        d = part._drag
        part._drag = None
        if hasattr(part, "_grab"):
            part._grab = None
        b._guard(lambda: d.end(cancel=True))
        return True
    return False


class EscHold(QObject):
    """This bridge's door to the kit's one Esc holder (rostrum_gui/drag_esc.py): held while a drag is open with a mouse
    button down (armed on a drag's start, drags._begin, and on any drag's first step, the bridge's _on_doc), let go when
    the document says the gesture ended ("change" or "reset") or the bridge's own drag ends. Not while no button is held:
    a scrub the panel keeps open between typed values, or a popover's live box, is no drag, and its own Esc stays."""

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge

    def cancel(self):
        cancel(self.b)

    def arm(self):
        if QGuiApplication.mouseButtons() != Qt.MouseButton.NoButton:
            ESC.hold(self.cancel)

    def disarm(self):
        ESC.let_go(self.cancel)


def drag_open(b) -> bool:
    """A drag is held now (the bridge's, a scrub, or a part's)."""
    if b._drag is not None or (getattr(b, "_kit", None) is not None and b._kit.scrub is not None):
        return True
    return any(_open(getattr(p, "_drag", None)) for p in _owners(b))


def watch(b) -> EscHold:
    """Esc-cancel for this bridge (kept by the caller)."""
    return EscHold(b)
