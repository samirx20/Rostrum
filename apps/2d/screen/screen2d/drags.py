"""Rostrum2D's drags: move a layer on the canvas (or, in an auto layout, change its slot), move a key on the
timeline, and move or trim a layer's bar on the timeline. Each is one doc.gesture = one undo step. A slot mix-in for Bridge2D (see rostrum_gui/parts.py)."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_core.keys import keys_of, marked
from rostrum2d import fields as F, ops_timing
from rostrum2d.evaluate import resolve
from rostrum2d.retime import END_OF_COMP
from rostrum_gui.edits import Drag
from rostrum_gui.parts import SlotMixin

from . import bounds, exprs, key_moves, layout_drag, route, time_snap
from .bar_drag import PARTS, BarGrab


class DragSlots(SlotMixin):
    @Slot(result=bool)
    def beginMove(self):
        return self._begin_move(False)

    @Slot(result=bool)
    def beginCopyMove(self):
        """Alt+drag on the canvas: the picked layers stay, copies of them (just above, as Ctrl+D makes) are picked and
        dragged. The copy and the move are one gesture, so one undo step takes both back."""
        return self._begin_move(True)

    def _begin_move(self, copy: bool) -> bool:
        layer = bounds.layer_of(self.doc, self._sel) if self._sel else ""
        if not layer:
            return False
        self._frames = {b["id"]: b for b in bounds.boxes(self.placed(), self._t)}      # each layer's parent frame, for the drag
        slots = layout_drag.begin(self.doc, self.placed(), layer, self._t)      # in an auto layout: change slot
        label = f"Move {self.label_of(self.doc.item(layer))}"
        if slots:
            return self._begin(label, slots)
        if any(exprs.drives(self.doc.item(layer), a) for a in ("x", "y")):
            self._fail("Error: move: x or y is driven by an expression; clear it first (the cross on its row).")
            return False
        more = self._multi.extras()
        p = resolve(self.placed_item(layer), self._t)          # keys on a marker placed
        ok = self._begin_many([layer] + more, copy) if more else self._begin(label if not copy else f"Copy {label[5:]}", (layer, p["x"], p["y"]))
        if ok and copy:
            ok = self._copy_in_drag([layer] + more)
        if ok:
            self._snap.begin(self._grabbed())           # what the drag may snap to (snapper.py)
        return ok

    def moving_many(self) -> bool:
        """Several layers moved on the canvas: a step changes their places only, so the timeline's rows and the panel
        (mixed values) follow at the drop; rebuilding 200 layers' rows every step cost tens of ms a move."""
        return self._drag is not None and isinstance(self._grab, list)

    def holds_panel(self) -> bool:
        """The kit's hook (bridge_select): Alt+drag's copies, picked inside the drag, get their panel at the drop."""
        return self.moving_many()

    def _grabbed(self) -> list:
        """The layers this drag moves."""
        return [g[0] for g in self._grab] if isinstance(self._grab, list) else [self._grab[0]]

    def _copy_in_drag(self, layers) -> bool:
        """First step of an Alt+drag: copy the layers inside the open gesture, then move the copies from where the
        originals were (each copy sits just after its original in its parent's list)."""
        calls = [{"op": "layer.duplicate", "target": list(layers), "args": {"by_x": 0}}]   # on the original: the drag and its snapping start there
        if not self._guard(lambda: self._drag.preview(calls)):
            self.endDrag()
            return False
        copies = [self.doc.item(parent)[k][at + 1]["id"] for parent, k, at in (self.doc.parent_of(i) for i in layers)]
        was = {lay: (x, y) for lay, x, y in (self._grab if isinstance(self._grab, list) else [self._grab])}
        grab = [(c, *was[o]) for c, o in zip(copies, layers)]
        self._grab = grab if len(grab) > 1 else grab[0]
        self.selectMany(copies)
        return True

    def _begin_many(self, layers, copy=False) -> bool:
        """Several selected layers move together: one gesture, one undo step."""
        grab = []
        for lay in layers:
            item = self.doc.item(lay)
            if layout_drag.begin(self.doc, self.placed(), lay, self._t) or any(exprs.drives(item, a) for a in ("x", "y")):
                self._fail(f"Error: move: {self.label_of(item)} is placed by an auto layout or an expression; select it alone to move it.")
                return False
            p = resolve(self.placed_item(lay), self._t)
            grab.append((lay, p["x"], p["y"]))
        return self._begin(f"{'Copy' if copy else 'Move'} {len(layers)} layers", grab)

    @Slot(float, float)
    def moveBy(self, dx, dy):
        """Total offset from where the drag started, in composition px: value.set x / y at the playhead (in an
        auto layout: layer.arrange to the slot nearest the pointer)."""
        if self._drag is None or not isinstance(self._grab, (dict, tuple, list)):
            return
        if not isinstance(self._grab, dict):
            dx, dy = self._snap.move(dx, dy)            # Shift: straight; then snapping (snapper.py)
        ox, oy = dx, dy
        if isinstance(self._grab, list):
            calls = []
            for lay, x0, y0 in self._grab:
                item = self.doc.item(lay)
                dx, dy = self._parent_drag(lay, ox, oy)
                calls += [route.value_call(item, "x", round(x0 + dx, 2), self.own_t(lay)), route.value_call(item, "y", round(y0 + dy, 2), self.own_t(lay))]
            self._guard(lambda: self._drag.preview(calls))
            return
        if isinstance(self._grab, dict):
            self._guard(lambda: self._drag.preview([layout_drag.call(self.doc, self._grab, dx, dy)]))
            return
        layer, x0, y0 = self._grab
        item = self.doc.item(layer)
        dx, dy = self._parent_drag(layer, dx, dy)
        self._guard(lambda: self._drag.preview([route.value_call(item, "x", round(x0 + dx, 2), self.own_t(layer)),
                                                route.value_call(item, "y", round(y0 + dy, 2), self.own_t(layer))]))

    def _parent_drag(self, layer, dx, dy):
        """The drag as the layer's parent sees it: a layer inside a turned or scaled group moves along the group's axes."""
        b = getattr(self, "_frames", {}).get(layer)
        return bounds.parent_delta(b, dx, dy) if b else (dx, dy)

    @Slot(str, result=bool)
    def beginKeyDrag(self, key_id):
        """A single picked key (key_select.py picks it first; keys never enter the layer selection)."""
        self._key_from = self.placed_item(key_id)["t"]
        self._found = time_snap.targets(self, skip_keys=[key_id])        # what it may snap to (time_snap.py)
        self._ends = key_moves.ends_of(self, {bounds.layer_of(self.doc, key_id)})   # the layer's end follows a key past it
        return self._begin("Move key", key_id)

    @Slot(float, float)
    def keyDragTo(self, t, snap=0.0):
        """`snap`: seconds within which the key lands on a marker, the playhead, another key or bar end, a beat
        (time_snap.py; 0 = Ctrl held: free) instead of the nearest frame."""
        if self._drag is None or not isinstance(self._grab, str):
            return
        c, key = self.comp(), self.placed_item(self._grab)
        t, caught = time_snap.snap(t, self._found, snap, c["fps"])
        t = min(max(t, 0.0), c["duration"])
        owner = self.placed_item(self.doc.parent_of(key["id"])[0])
        if any(k["id"] != key["id"] and abs(k["t"] - t) < 1e-6 for k in keys_of(owner, key["prop"])):
            return                       # another key of this field is there: stay at the last free time
        self.timeSnap.show(t - self._key_from, c["fps"], caught, t, bounds.layer_of(self.doc, key["id"]))
        to = marked.moved(key["ref"], t - key["t"]) if "ref" in key else t - self.offset(owner["id"])   # on a marker: stays on it; else own seconds
        calls = [{"op": "key.set", "target": [key["id"]], "args": {"t": to}},
                 *key_moves.end_follows(self._ends, {bounds.layer_of(self.doc, key["id"]): t})]
        self._guard(lambda: self._drag.preview(calls))

    @Slot(str, str, float, result=bool)
    def beginBarDrag(self, layer_id, part, t0):
        """Press on a layer bar of the timeline: part "move" (the bar), "start" or "end" (its edges); t0 = the time under
        the pointer, composition seconds. False (and the status says why) for what can't move."""
        item = self.placed_item(layer_id) if self.doc.has(layer_id) else None
        if item is None or item.get("type") not in F.LAYERS or part not in PARTS:
            self._fail(f"Error: bar drag: {layer_id!r} is not a layer bar I can {part}.")
            return False
        if item.get("locked"):
            self._fail(f"Error: {self.label_of(item)} is locked; unlock it to move it in time.")
            return False
        ops_timing.use_project(self.doc.folder)
        fps, end = self.comp()["fps"], item.get("end", END_OF_COMP)
        others = [i for i in self.selected_layers() if i != layer_id and not self.doc.item(i).get("locked")]             if part == "move" and layer_id in self.selected_layers() else []      # a selected bar takes the others along
        moving = [layer_id, *others]
        found = time_snap.targets(self, carried=moving) if part == "move" else time_snap.targets(self, skip_layers=moving)
        grab = BarGrab(layer_id, part, t0, item.get("start", 0.0), end if end < END_OF_COMP else self.comp()["duration"], fps, others, found)
        if not others:
            self.select(layer_id)
        return self._begin({"move": "Move in time", "start": "Trim start", "end": "Trim end"}[part], grab)

    @Slot(float, float)
    def barDragTo(self, t, snap_seconds=0.0):
        """The pointer is at `t` (composition seconds): the edge snaps within `snap_seconds` (time_snap.py; 0 = Ctrl
        held: free), else to a whole frame."""
        if self._drag is None or not isinstance(self._grab, BarGrab):
            return
        g = self._grab
        calls = g.calls(t, snap_seconds, self.placed_item(g.layer).get("start", 0.0))
        self.timeSnap.show(g.moved, g.fps, g.caught, g.edge, g.layer)
        if calls:
            self._guard(lambda: self._drag.preview(calls))

    @Slot()
    def endDrag(self):
        d, g, self._drag, self._grab = self._drag, self._grab, None, None
        held, self.held_view = self.held_view, None     # a camera-key drag held the view: it follows the camera again
        self._snap.end()                                # the snap lines go with the drag
        self.timeSnap.clear()                           # and the "+6 f" label
        if d is not None and isinstance(g, BarGrab) and g.tie_calls():      # let go on a marker: the layer is tied to it
            self._guard(lambda: d.preview(g.tie_calls()))
        if d is not None:
            self._guard(lambda: self._done(d.end(), ""))
        if held is not None and self._scene is None:    # drawn once, at the drop
            self._show()

    def _begin(self, label, grab) -> bool:
        self.endDrag()

        def go():
            self._drag, self._grab = Drag(self.doc, self.who, label), grab
        return self._guard(go)
