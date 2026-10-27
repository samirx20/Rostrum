"""The selected layers as the canvas and the layers list use them: the kit's ONE selection (`bridge.selection`,
`selectMany`; the primary first) read as layers, their boxes for the outlines, and the ways to change it by hand:
Shift+click on the canvas, Ctrl+click / Shift+click in the layers list, the rubber band, and which piece a click picks
(picking.py), and the Gap row (GapRow.qml: the gap of 3+ evenly spaced layers, typed or scrubbed through
layer.distribute {gap}). A QObject part, read in QML as `backend.multi`."""
from __future__ import annotations

from rostrum2d import boxes as B
from rostrum_gui import news
from rostrum_gui.after_frame import AfterFrame
from rostrum_gui.edits import Drag

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui.selection_rules import click

from . import band, bounds, picking, snap, under_menu
from .handle_kinds import dressed
from .group_slots import union


class Multi(QObject):
    boxesChanged = Signal()                                 # the outlines and handles on the canvas (boxes, groupBox)
    pickedChanged = Signal()                                # which layers (count, ids, lit: the list's rows)
    rideChanged = Signal()
    gapChanged = Signal()                                   # the Gap row (in the settings panel)
    bandChanged = Signal()                                  # what the growing rubber band would pick (bandPath)

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        self._known = None                                  # (selection, document data, its layers)
        self._even, self._drag = (None, {}), None           # ((selection, data, time), the Gap row); a Gap scrub
        self._band = ((), "")                               # (the ids the rubber band would pick, their outlines)
        # only news, and each kind of news on its own signal: one `changed` for all six made every reader of any of
        # them run again whenever one moved (each box arriving with the picture re-lit every timeline row; ~37 ms
        # of a Ctrl+G)
        self._boxes = self._group = (None, None)            # (what they were made from, the boxes): see `_made`
        self._path = (None, None, "")                       # (the boxes, skip, outlinePath's path)
        # the Gap row is the settings panel's and lands with it, the frame after (it reads every picked layer's box:
        # 200 layers ~5-10 ms inside the pick's own frame)
        gap = AfterFrame(news.relay(self, "gapChanged"), self)
        for told in [news.relay(self, n) for n in ("boxesChanged", "pickedChanged", "rideChanged")] + [gap.ask]:
            for s in (bridge.selectedItemsChanged, bridge.outlineChanged, bridge.shownChanged):
                s.connect(told)

    def _made(self):
        """What the boxes are made from: the picked layers and the picture on screen (shown.py). A cache keyed on it
        can't go stale the way one cleared by a list of signals did (one missed and a pick drew no outline)."""
        return (tuple(self.layers()), self.b.shown_placed(), self.b.shown_t())

    @Property("QVariantList", notify=boxesChanged)
    def boxes(self):
        """The box of every selected layer (the primary first): the outlines the canvas draws, as the picture on screen
        shows them (shown.py; a layer newer than the picture has none yet). Made once per change and kept: each outline
        reads the whole list (`backend.multi.boxes[index]`), so remaking it per read made a pick of n layers n x n boxes
        (48 layers: 2,500 boxes, ~100 ms). Only one layer's box draws knobs, so only then is it dressed (its knobs:
        handle_kinds.dressed): QML copies the whole list on every read, and 200 dressed boxes cost ~3x plain ones."""
        made = self._made()
        if not _same(self._boxes[0], made):
            got = self.b.shown_boxes(self.layers())
            self._boxes = (made, [dressed(b) for b in got] if len(got) == 1 else got)
        return self._boxes[1]

    @Property("QVariantList", notify=boxesChanged)
    def knobBoxes(self):
        """`boxes` while at most one layer is picked (its outline item with knobs), else []: several draw as one shape
        (outlinePath), so the canvas's outline items never copy the whole list (QML copies a list on every read: 200
        boxes were ~ms a reader, on every pick and every box change)."""
        return self.boxes if len(self.layers()) <= 1 else []

    @Slot(str, result=str)
    def outlinePath(self, skip):
        """With several layers picked, every one's turned outline as ONE svg path (composition px): the canvas draws
        them as one shape, not an item with knobs each (48 layers: ~250 ms of items -> a string). `skip`: the layer
        whose outline something else is drawing now (painting its true edge, typing). Read `groupBox` (same news, a
        small map) in the binding so it runs again when they change; `boxes` there copied all of them into QML."""
        boxes = self.boxes                                  # (made once per change: `_made`)
        if self._path[0] is boxes and self._path[1] == skip:   # both news (picked, boxes) re-read it: built once
            return self._path[2]
        out = []
        for b in boxes:
            if b.get("id") != skip and b.get("w") is not None:
                out.append(band.outline(b))
        self._path = (boxes, skip, " ".join(out))
        return self._path[2]

    @Property("QVariantMap", notify=boxesChanged)
    def groupBox(self):
        """The one box round all the selected layers (their handles: group_slots.py); {} for fewer than two."""
        made = self._made()
        if not _same(self._group[0], made):
            boxes = self.b.shown_boxes(self.layers())
            self._group = (made, dressed(union(boxes)) if len(boxes) > 1 else {})
        return self._group[1]

    @Property("QVariantMap", notify=rideChanged)
    def ride(self):
        """The path the primary selected layer (or the camera) rides, with the words the canvas shows for it
        (its `id`, `label`). {} when the selection rides nothing."""
        ids = self.layers()
        rider = self.b.doc.item(ids[0]) if ids else {}
        path = rider.get("ridePath", "")
        if not path or not self.b.doc.has(path):
            return {}
        what = "Camera" if rider.get("type") == "camera" else rider.get("name") or ids[0]
        return {"id": path, "label": f"{what} rides {self.b.doc.item(path).get('name') or path}"}

    @Property("QVariantMap", notify=gapChanged)
    def gap(self):
        """The Gap row: {axis "x" | "y", gap px} when 3+ picked layers in one place sit equally apart along an axis
        (base G, snap.even within 0.5 px; across first); {} otherwise, and the row is absent."""
        ids, key = self.layers(), (tuple(self.b.selection), self.b.doc.data, self.b._t)
        if self._even[0] != key:
            self._even = (key, self._gap_of(ids) if len(ids) >= 3 else {})
        return self._even[1]

    def _gap_of(self, ids):
        doc = self.b.doc
        parents = {doc.parent_of(i)[0] for i in ids}
        if len(parents) > 1 or doc.item(parents.pop()).get("layout", "none") != "none":
            return {}
        t = self.b.own_t(ids[0])
        boxes = [B.box(doc.item(i), t) for i in ids]
        for axis in ("x", "y"):
            g = snap.even(boxes, axis)
            if g is not None:
                return {"axis": axis, "gap": round(g, 2)}
        return {}

    def _distribute(self, axis, gap):
        ids = self.layers()
        return {"op": "layer.distribute", "target": ids, "args": {"axis": axis, "gap": round(gap, 4), "at": self.b.own_t(ids[0])}}

    @Slot(float)
    def setGap(self, gap):
        """A typed gap: the layers re-spaced from the first (leftmost or topmost), one change."""
        if self.gap:
            call = self._distribute(self.gap["axis"], gap)
            self.b.guard(lambda: self.b.done(self.b.doc.apply([call], self.b.who, label="Gap"), ""))

    @Slot()
    def beginGap(self):
        self.endGap()
        if self.gap:
            self._axis = self.gap["axis"]

            def go():
                self._drag = Drag(self.b.doc, self.b.who, "Gap")
            self.b.guard(go)

    @Slot(float)
    def gapTo(self, gap):
        """A Gap scrub's step: the preview of the whole scrub (one change at its end)."""
        if self._drag is not None:
            call = self._distribute(self._axis, gap)
            self.b.guard(lambda: self._drag.preview([call]))

    @Slot()
    def endGap(self):
        d, self._drag = self._drag, None
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))

    @Property(int, notify=pickedChanged)
    def count(self):
        return len(self.layers())

    @Property("QVariantList", notify=pickedChanged)
    def ids(self):
        """The selected layers (an effect, mask or key selected counts as its layer): the rows the list lights."""
        return self.layers()

    @Property("QVariantMap", notify=pickedChanged)
    def lit(self):
        """{row id: "sel" | "in"}: how each layers-list row is lit, read once per change by the list (LayerRows.qml), so
        a row looks itself up instead of each row reading the selection again (~5 ms a pick over 20 rows): the selected
        item's row and, with several picked, every picked layer "sel"; one picked layer whose key, effect or mask is
        what is selected "in"."""
        ids = self.layers()
        out = dict.fromkeys(ids, "sel" if len(ids) > 1 else "in")
        if self.b.selected:
            out[self.b.selected] = "sel"
        return out

    def layers(self) -> list[str]:
        """Worked out once per selection and document state (the document is a new object on every change): the
        overlays and the list read it ~80 times a pick."""
        sel, data = tuple(self.b.selection), self.b.doc.data
        if self._known is None or self._known[0] != sel or self._known[1] is not data:
            out = []
            for i in sel:
                layer = bounds.layer_of(self.b.doc, i) if self.b.doc.has(i) else ""
                if layer and layer not in out:
                    out.append(layer)
            self._known = (sel, data, out)
        return list(self._known[2])

    def extras(self) -> list[str]:
        return self.layers()[1:]

    def _set(self, ids: list[str]):
        """Select these layers together: the first is the primary (none: the composition)."""
        self.b.selectMany(ids) if ids else self.b.select(self.b.comp_id)

    @Slot(str, result=bool)
    def has(self, layer_id):
        return layer_id in self.layers()

    @Slot(str)
    def toggle(self, layer_id):
        """Shift+click on the canvas, Ctrl+click in the list: add the layer to the selection, or take it out."""
        self._set(click(self.layers(), None, layer_id, {"ctrl"}, "list")[0])      # the kit's rule (INTERACTION 1.3)

    @Slot(str)
    def selectRange(self, layer_id):
        """Shift+click in the layers list: every layer row from the primary to this one, as the list shows them."""
        rows, picked = [r["id"] for r in self.b.layer_rows() if r["row"] == "layer"], self.layers()
        here = picked[0] if picked else layer_id
        run = click(picked, here, layer_id, {"shift"}, "list", rows)[0]      # the kit's rule (INTERACTION 1.3)
        self._set([here] + [i for i in run if i != here] if here in run else run)     # the primary stays first

    @Slot(float, float, str, result=str)
    def target(self, x, y, mode):
        """What a click at (x, y) composition px would select, without selecting it ("" = nothing painted there).
        mode: "click" (the outermost group, or the piece among its siblings once inside it), "deep" (Ctrl: the piece
        itself), "in" (double-click: one level further in than the selection)."""
        chain = bounds.pick_chain(self.b.placed(), self.b._t, x, y)
        sel = self.layers()[0] if self.layers() else ""
        return picking.choose(chain, sel, picking.groups_of(self.b.doc, sel) if sel else [], mode)

    def _depth(self):
        sel = self.layers()[0] if self.layers() else ""
        return sel, (picking.groups_of(self.b.doc, sel) if sel else [])

    @Slot(float, float, str, result=str)
    def pickBehind(self, x, y, mode):
        """Alt+click at (x, y): select the next layer below the pick there (mode "click", or "deep" for Ctrl+Alt: the
        pieces), wrapping to the top; returns it ("" = nothing painted there: the composition)."""
        sel, groups = self._depth()
        hit = picking.behind(picking.levels(bounds.under_chains(self.b.placed(), self.b._t, x, y), sel, groups, mode), sel)
        self._set([hit] if hit else [])
        return hit

    @Slot(float, float, result="QVariantList")
    def underMenu(self, x, y):
        """The canvas right-click's first row, Select layer ▸ (under_menu.py); [] with fewer than two layers there."""
        sel, _ = self._depth()
        return under_menu.entries(self.b, bounds.under_chains(self.b.placed(), self.b._t, x, y), sel)

    @Slot(float, float, str, result=str)
    def pick(self, x, y, mode):
        """A click at (x, y): select what `target` says (nothing painted there: the composition)."""
        hit = self.target(x, y, mode)
        self._set([hit] if hit else [])
        return hit

    @Slot(float, float, float, float, str, result=int)
    def boxSelect(self, x0, y0, x1, y1, mods=""):
        """The rubber band (composition px), by the kit's rule (selection_rules.box, INTERACTION 1.3): every layer it
        touches, as its outermost group (never a locked one); `mods` "shift" adds them to the selection, "ctrl" picks
        the deepest pieces instead (not groups). Returns how many are selected."""
        ids = band.picks(self.b, self.layers(), (x0, y0, x1, y1), mods)
        self.endBand()
        self._set(ids)
        return len(ids)

    @Property(str, notify=bandChanged)
    def bandPath(self):
        """While the rubber band grows: the outlines of what letting go now would pick, as one svg path (band.py)."""
        return self._band[1]

    @Slot(float, float, float, float, str)
    def bandTo(self, x0, y0, x1, y1, mods=""):
        """The rubber band at (x0, y0)-(x1, y1) on a pointer move: the layers it would pick light up (bandPath)."""
        got = band.preview(self.b, self.layers(), (x0, y0, x1, y1), mods, self._band)
        if got is not self._band:
            self._band = got
            self.bandChanged.emit()

    @Slot()
    def endBand(self):
        if self._band[1]:
            self._band = ((), "")
            self.bandChanged.emit()


def _same(was, now) -> bool:
    """Multi._made's keys alike: the same layers and time, and the very same picture (not an equal one: no deep compare)."""
    return was is not None and was[0] == now[0] and was[1] is now[1] and was[2] == now[2]
