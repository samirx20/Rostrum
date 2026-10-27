"""A gizmo drag drawn live (SPEC 4.1), for gizmo_qt.py: while the pointer moves, the dragged item's new place goes
straight to the window's own view as one light `xform` request (ENGINE_CONTRACT.md; view_item.ViewLink.xform); the
document changes once, at the drop (one undo step, through the same edit calls as before). Where the view can't show
the move exactly that way, the drag previews each move in the document as before; `why_not` is the one place that says
which. No Qt here beyond the link it is handed.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Slot
from rostrum3d import aim, fields as F, resolve

from . import gizmo as G
from .gizmo_drag import MOVE, TURN, SCALE, PIVOT

XFORM = MOVE + TURN + SCALE                  # what the light request sets: translate, rotateXYZ, scale
_REFS = ("aimItem", "follow", "stick", "focusItem")     # fields that make another item depend on this one's place
_REFUSED = [False]                           # the view refused an xform once (an older build): every drag previews


def why_not(bridge, vp, c) -> str:
    """"" when the drag `c` (gizmo_qt's context) can be drawn live; else why it previews each move in the document."""
    it = c["it"]
    if vp.link is None:
        return "the engine program draws this view"
    if _REFUSED[0]:
        return "the window's view can't move an item by itself (an older build)"
    if c["mesh"]:
        return "Edit mesh"
    if it["type"] in ("bone", "rig"):
        return f"a {it['type']}'s turn is worked out per frame"
    inside = _subtree(it)
    if any(i.get("bones") and i.get("skinned", True) for i in inside):
        return "a mesh bent by its bones is posed per frame"
    if any(i.get("aim", "none") != "none" or i.get("follow") or i.get("stick") for i in inside):
        return "it (or something inside it) aims, follows or sticks: worked out per frame"
    if _steps(bridge, it):
        return "it is on 2s or 3s"
    ids = {i["id"] for i in inside}
    if vp.cam.mode in ("shot", "light") and (vp.cam.light if vp.cam.mode == "light" else vp.cam.camera) in ids:
        return "the view looks through it"
    if any(i["id"] not in ids and any(i.get(r) in ids for r in _REFS if r != "aimItem" or i.get("aim") == "item")
           for i in bridge.doc.items()):
        return "another item aims at, follows, sticks to or focuses on it"
    return ""


def _subtree(it) -> list[dict]:
    out, stack = [], [it]
    while stack:
        i = stack.pop()
        out.append(i)
        stack += i.get("children", [])
    return out


def _steps(bridge, it) -> bool:
    """The item or a group it is in holds its values for 2 or 3 frames (resolve.Frames.step)."""
    doc, id_ = bridge.doc, it["id"]
    while id_ is not None:
        if F.STEPS.get(doc.item(id_).get(resolve.TIMING, "smooth"), 1) > 1:
            return True
        id_ = doc.parent_of(id_)[0]
    return False


def fields(it, values: dict) -> dict:
    """The xform request's numbers for the item at `values` (its own fields): x y z the origin, the pivot resolved as
    compile.py does (resolve.pivoted), and only the fields the item has."""
    has = {p.name for p in F.FIELDS[it["type"]]}
    out = {k: float(values[k]) for k in XFORM if k in has}
    if any(values.get(p) for p in PIVOT):
        out.update(zip(MOVE, resolve.pivoted({**values, **{k: values.get(k, 1.0) for k in SCALE}})))
    return out


class Sender:
    """At most one xform on its way; a newer move replaces the one waiting (newest wins), so the view never falls
    behind the pointer. A refusal is said on the console and `refused(error)` takes the drag back to the per-move
    preview (a view built before `xform`: every later drag too)."""

    def __init__(self, link, refused):
        self.link, self.refused = link, refused
        self._busy, self._next = False, None
        self.sent = 0

    def send(self, item: str, values: dict):
        if self._busy:
            self._next = (item, values)
        else:
            self._go(item, values)

    def drop_waiting(self):
        """At the drop: the document's scene takes over; a move still waiting would undo it."""
        self._next = None

    def _go(self, item, values):
        self._busy, self.sent = True, self.sent + 1
        self.link.xform(item, values, self._answered)

    def _answered(self, out):
        self._busy = False
        if isinstance(out, str):
            self._next = None
            print(f"rostrum3d: this gizmo drag previews in the document instead: {out}", file=sys.stderr)
            _REFUSED[0] = _REFUSED[0] or 'no request "xform"' in out       # a view built before xform: every drag
            return self.refused(out)
        if self._next is not None:
            nxt, self._next = self._next, None
            self._go(*nxt)


class LiveDrag:
    """gizmo_qt.Gizmo's live moves, its drop and its Esc (the drag's state is the Gizmo's: _drag, _live, _grab)."""

    def _live_move(self, c, vals):
        self._live.send(c["it"]["id"], fields(c["it"], vals))
        pw, origin, turn = G.item_frame(c["pw"], vals)
        self._ctx = {**c, "origin": origin, "turn": turn, "own": G.columns(aim._mul(pw[0], turn))}
        self._place()

    def _unlive(self, _why):
        """The view refused the live move (Sender): the rest of this drag previews in the document."""
        if self._live is not None and self._drag is not None:
            self._live = None
            self.bridge._guard(lambda: self._drag.preview(self._grab["calls"]))

    @Slot()
    def end(self):
        """The drop: one change (a live drag's whole move at once: the document's new scene takes over the view)."""
        d, sender, self._drag, self._live, self._label = self._drag, self._live, None, None, ""
        if d is not None:
            calls = self._grab["calls"] if sender is not None and self._grab["calls"] else None
            if sender is not None:
                sender.drop_waiting()
            if not self.bridge._guard(lambda: self.bridge._done(d.end(calls=calls), "")) or (sender and not calls):
                self._put_back(sender)          # nothing changed (or the change was refused): the view shows the press
        self._refresh()

    @Slot(result=bool)
    def cancel(self):
        """Esc during a drag (esc3d.py): the item goes back where it was, no history step, the drag ends."""
        d, sender, self._drag, self._live, self._label = self._drag, self._live, None, None, ""
        if d is None:
            return False
        self.bridge._guard(lambda: d.end(cancel=True))
        self._put_back(sender)
        self._refresh()
        return True

    def _put_back(self, sender):
        """After a live drag that changed nothing: the press-time place at once, then the document's scene again
        (the xform dropped the item's animation from the live stage until the next scene)."""
        if sender is None or not sender.sent:
            return
        c = self._grab["ctx"]
        if c.get("copy") is not None:                   # a picked copy (copies_gizmo.py)
            return self._copy_put_back(sender)
        sender.send(c["it"]["id"], fields(c["it"], c["v"]))
        if c["it"].get("keys"):
            self.vp.link._forget_scene()
            self.vp.redraw()

