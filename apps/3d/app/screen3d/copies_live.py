"""Copies drawn live (brief 24): dragging Count or a Spacing amount in the settings panel sends the window's own view one
light `copies` request per pointer move (ENGINE_CONTRACT.md: it lays that copies item again on the stage it holds, no new
scene); the document changes once, when the pointer lets go (one undo step, the field's own `copies.set`). The same
request moves a held copy while the gizmo drags it (copies_gizmo.py). Where the view can't (an older build, the engine
program draws the view), the drag previews each move in the document as it always did.

`Live` is the one sender: at most one request on its way, a newer move replaces the one waiting (newest wins), so the
view never falls behind the pointer; `timings` keeps the engine's own ms per answer (the walk reads it). `Scrubs` is
Bridge3D's mix-in: the kit's beginScrub / scrub / endScrub / cancelScrub, live where it can; a selected material's
numbers and colours go live the same way (a `material` request, material_live.py). No Qt beyond the link.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Slot
from rostrum3d import copies_fields as CF, fields as F
from rostrum_gui import kit_state

# The kit keeps an app from redefining its own names unless they are HOOKS (kit_state.py); the start, moves and end of a
# drag are not on that list yet. This app takes them over for a copies item's numbers; the one-line request for the kit's
# list is in brief 24's report. (Read at each check, so adding here, before the first bridge is made, is enough.)
kit_state.HOOKS = kit_state.HOOKS | {"beginScrub", "scrub", "endScrub", "cancelScrub"}
LIVE_PARAMS = {p.name for p in CF.COPIES if p.type == "number" and p.name not in {q.name for q in CF.TRANSFORM}}
_REFUSED = [False]                     # the view refused a `copies` request once (an older build): every drag previews


def request(item: str, props: dict | None = None, held: list | None = None) -> dict:
    """The live request: the copies item's props to change (any of the compiled node's) and/or its held copies."""
    body: dict = {"item": item}
    if props:
        body["props"] = props
    if held is not None:
        body["held"] = held
    return {"copies": body}


class Live:
    def __init__(self, link, refused=None):
        self.link, self.refused = link, refused
        self._busy, self._next = False, None
        self.sent, self.timings, self.counts = 0, [], []

    def send(self, item: str, props: dict | None = None, held: list | None = None):
        self.post(request(item, props, held))

    def post(self, req: dict):
        """Any live request (a copies item's, a material's: material_live.py), newest wins."""
        if self._busy:
            self._next = req
        else:
            self._go(req)

    def drop_waiting(self):
        """At the drop: the document's own scene takes over; a move still waiting would undo it."""
        self._next = None

    def _go(self, req):
        self._busy, self.sent = True, self.sent + 1
        self.link.post(req, self._answered)

    def _answered(self, out):
        self._busy = False
        if isinstance(out, str):
            self._next = None
            print(f"rostrum3d: this drag previews in the document instead: {out}", file=sys.stderr)
            _REFUSED[0] = _REFUSED[0] or 'no request "copies"' in out
            from . import material_live
            material_live.REFUSED[0] = material_live.REFUSED[0] or 'no request "material"' in out
            if self.refused:
                self.refused(out)
            return
        self.timings.append(float(out.get("ms", 0.0)))
        if out.get("count") is not None:
            self.counts.append(out["count"])
        if self._next is not None:
            nxt, self._next = self._next, None
            self._go(nxt)

    @property
    def idle(self) -> bool:
        return not self._busy and self._next is None


def available(bridge) -> bool:
    vp = getattr(bridge, "viewport", None)
    return vp is not None and vp.link is not None and vp.link.item is not None and not _REFUSED[0]


class Scrubs:
    """Bridge3D's scrub slots for a copies item's Count and Spacing. The field's own widget does the drag (the kit's
    InspectorRow: scrubStarted, then `scrub` per move, scrubEnded); here the moves go to the view, and the release is
    one `copies.set`-style change through the bridge's own edit call."""
    _live = None                       # the open live drag: {param, send, value, start, item}
    _dropped = ""                      # the field whose drag Esc cancelled: its moves change nothing until the release

    @property
    def scrubbing(self) -> bool:
        """A field's number is being dragged (live or through the kit): what Esc cancels (esc3d.py)."""
        return self._live is not None or self._kit.scrub is not None

    def cancel_drag(self):
        """Esc in the middle of a number drag: the value goes back, no history step, and the rest of this drag (the
        field still has the mouse) changes nothing until it is let go."""
        self._dropped = self._live["param"] if self._live is not None else self._kit.scrub.name
        self.cancelScrub()

    def _live_req(self, param: str):
        """The live request maker for a drag of `param` on the one selected item: a copies item's numbers, a material's
        numbers and colours (material_live.py); None when this drag can't be live."""
        from . import material_live
        if len(self.selection) != 1 or not self.selected or not self.doc.has(self.selected):
            return None
        it = self.doc.item(self.selected)
        if it["type"] == "copies" and param in LIVE_PARAMS and available(self):
            return lambda v: request(it["id"], {param: v})
        if it["type"] == "material" and material_live.ok(self, param):
            return lambda v: material_live.request(it["id"], param, v)
        return None

    @Slot(str)
    def beginScrub(self, param):
        if self._dropped == param:
            return
        self._dropped = ""
        self._live_end(commit=False)
        req = self._live_req(param)
        if req is None:
            return super().beginScrub(param)
        it = self.doc.item(self.selected)
        self._live = {"param": param, "item": it["id"], "start": it.get(param, F.param(it["type"], param).default),
                      "value": None, "req": req, "send": Live(self.viewport.link, lambda _why: self._live_refused())}

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        if self._dropped == param:
            return
        lv = self._live
        if lv is not None and lv["param"] == param:
            lv["value"] = value
            lv["send"].post(lv["req"](value))
            return
        super().scrub(param, value)

    @Slot()
    def endScrub(self):
        if self._dropped:
            self._dropped = ""
            return
        if self._live is not None:
            return self._live_end(commit=True)
        super().endScrub()

    @Slot()
    def cancelScrub(self):
        if self._live is not None:
            return self._live_end(commit=False)
        super().cancelScrub()

    def _live_refused(self):
        """The view refused the live request: the rest of this drag is previewed in the document (the kit's scrub)."""
        lv, self._live = self._live, None
        if lv is not None:
            super().beginScrub(lv["param"])
            if lv["value"] is not None:
                super().scrub(lv["param"], lv["value"])

    def _live_end(self, commit: bool):
        lv, self._live = self._live, None
        if lv is None:
            return
        lv["send"].drop_waiting()
        value = lv["value"]
        if value is None or value == lv["start"]:
            return
        if not commit:                 # Esc: the view goes back to what the document says
            lv["send"].post(lv["req"](lv["start"]))
            return
        self._last_live = lv["send"]
        self._guard(lambda: self._done(self.doc.apply([self.edit_call(lv["item"], lv["param"], value)], self.who,
                                                      label=self._edit_label(lv["item"], lv["param"], value)), ""))
