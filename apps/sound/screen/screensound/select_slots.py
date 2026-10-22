"""The bridge's selection as a list, the time range, and the one action list (a slot mix-in for SoundBridge, see
gui-kit parts.py). Click / Ctrl+click / Shift+click / box / Ctrl+A / Esc pick ids (selection.py); what is done with
them is action_slots.py (the one action list). Selecting is screen state, not
an undo step; every action is one change. The whole list goes to the kit's `selectMany` (H28: the settings panel
shows what the selected items share); the order picked, the Shift anchor and the time range stay here. After the
person's undo / redo, what that step touched is selected again (read from the change's `undoes` / `redoes`).
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from . import selection, timing


class SelectSlots:
    rangeChanged = Signal()
    picksChanged = Signal()

    @property
    def _picks(self) -> selection.Selection:
        if "_picks_" not in self.__dict__:
            self.__dict__["_picks_"] = selection.Selection()
            self.__dict__["_board"], self.__dict__["_area"] = {"items": []}, "arrange"
        return self.__dict__["_picks_"]

    # ---- reads for QML --------------------------------------------------------------------------------------
    @Property("QVariantList", notify=picksChanged)
    def selectedIds(self):
        return list(self._picks.ids)

    @Property("QVariantMap", notify=picksChanged)
    def picked(self):
        """id -> true for every selected id (what the lanes and the roll draw with the accent outline)."""
        return {i: True for i in self._picks.ids}

    @Property(str, notify=picksChanged)
    def selectionWords(self):
        """The count chip: "5 notes", "2 tracks" ("" for none)."""
        return selection.count_words(self._kinds())

    def selection_label(self, ids):
        """The kit's panel title and Ctrl K hints: one item's name, else Sound's count words ("5 notes")."""
        if len(ids) == 1:
            return super().selection_label(ids)
        return selection.count_words([self.doc.item(i)["type"] for i in ids])

    def _kinds(self):
        return [self.doc.item(i)["type"] for i in self._picks.ids]

    # ---- picking ----------------------------------------------------------------------------------------------
    @Slot(str)
    def select(self, item_id):
        """One item alone ("" = none)."""
        self._pick([item_id] if item_id else [])

    @Slot("QVariantList")
    def pickMany(self, ids):
        """Several ids at once ([] = none); the kit's own `selectMany` is called with the result."""
        self._pick([str(i) for i in ids])

    def _pick(self, ids, anchor=None):
        gone = [i for i in ids if not self.doc.has(i)]
        if gone:
            return self._fail(f'Error: select: no item "{gone[0]}".')
        self._picks.set(ids, anchor)
        self.selectMany(self._picks.ids)          # the kit: the settings panel + selectionChanged
        self.picksChanged.emit()

    @Slot(str, bool, bool)
    def clickSelect(self, item_id, ctrl, shift):
        """A click on an item or a track header: alone; Ctrl adds or removes; Shift = the run from the last one
        clicked (in time on one track; the tracks between two headers)."""
        p = self._picks
        if ctrl:
            return self._pick(p.toggle(item_id) and p.ids, p.anchor)
        if shift and p.anchor and self.doc.has(p.anchor):
            run = selection.run_between(self._order_of(p.anchor), p.anchor, item_id)
            if run:
                return self._pick(run, p.anchor)
        self._pick([item_id])

    def _order_of(self, item_id):
        if self.doc.item(item_id)["type"] == "track":
            return [t["id"] for t in self.doc.data.get("tracks", [])]
        row = next((r for r in self._view["rows"] if any(b["id"] == item_id for b in r["blocks"])), None)
        return selection.time_order(row["blocks"]) if row else []

    @Slot("QVariantList", float, float, bool)
    def boxSelect(self, track_ids, t0, t1, add):
        """A box dragged on empty lane space in the arrangement: what it touches on those tracks (Ctrl adds)."""
        got = [i for r in self._view["rows"] if r["id"] in track_ids for i in selection.in_box(r["blocks"], t0, t1)]
        self._box(got, add)

    @Slot(float, float, float, float, bool)
    def boxRoll(self, t0, t1, r0, r1, add):
        """A box in the Editor's piano roll / drum rows: keys (or drum rows) r0..r1, times t0..t1."""
        roll = self._view["roll"]
        self._box(selection.in_box(roll["blocks"], t0, t1, r0, r1, roll.get("drums")), add)

    def _box(self, got, add):
        base = self.__dict__.setdefault("_box_base", list(self._picks.ids) if add else [])
        self._pick([*base, *got] if add else got)

    @Slot()
    def endBox(self):
        self.__dict__.pop("_box_base", None)

    @Slot(str)
    def focusArea(self, area):
        """The area last clicked ("arrange" or "roll"): Ctrl+A takes everything of its kind there; its action bar
        shows."""
        if area != self._area:
            self._area = area
            self.picksChanged.emit()

    @Property(str, notify=picksChanged)
    def area(self):
        return self._area

    @Slot(str)
    def focusTrack(self, track_id):
        """A click on empty lane space: that track is the one the Editor shows and Paste goes to (not a selection)."""
        if self.doc.has(track_id) and track_id != self._track:
            self._track = track_id
            self._rebuild()

    @Slot(result="QVariantMap")
    def selectionExtent(self):
        """Where the selection is, for its action bar: t0, t1 (seconds), tracks (ids), lo / hi (piano roll keys, or
        drum rows for hits); {} for none (a time range alone: t0, t1)."""
        drawn = selection.blocks_by_id(self._view["rows"])
        bs = [drawn[i] for i in self._picks.ids if i in drawn]
        tracks = [i for i in self._picks.ids if self.doc.item(i)["type"] == "track"]
        if not bs:
            r = self._picks.range or ((0.0, self._length()) if tracks else None)
            return {"t0": r[0], "t1": r[1], "tracks": tracks, "lo": 0, "hi": 0} if r else {}
        drums = self._view["roll"].get("drums") or []
        rows = [k for b in bs for k in b.get("keys", [])] or [drums.index(b["drum"]) for b in bs if b.get("drum") in drums]
        return {"t0": min(b["t"] for b in bs), "t1": max(b["t"] + b["dur"] for b in bs),
                "tracks": list(dict.fromkeys(b["track"] for b in bs)), "lo": min(rows, default=0), "hi": max(rows, default=0)}

    @Slot()
    def selectAll(self):
        if self._area == "roll":
            return self._pick([b["id"] for b in self._view["roll"]["blocks"]])
        tracks = [i for i in self._picks.ids if self.doc.item(i)["type"] == "track"] or \
            [r["id"] for r in self._view["rows"]]
        self._pick([b["id"] for r in self._view["rows"] if r["id"] in tracks for b in r["blocks"]])

    @Slot(result=bool)
    def clearSelection(self):
        """Esc: a time range goes first, then the selection. False when there was nothing to clear."""
        if self._picks.range:
            self.clearRange()
            return True
        if self._picks.ids:
            self._pick([])
            return True
        return False

    # ---- the time range (the ruler) ---------------------------------------------------------------------------
    @Property("QVariantList", notify=rangeChanged)
    def timeRange(self):
        return list(self._picks.range) if self._picks.range else []

    @Slot(float, float, bool)
    def setRange(self, t0, t1, free):
        """A drag on the ruler: a time range, snapped to the grid unless free (Ctrl)."""
        a, b = sorted((timing.snap(t0, self.doc.data, free), timing.snap(t1, self.doc.data, free)))
        self._picks.range = (a, b) if b - a > 1e-3 else None
        self.rangeChanged.emit()
        self.selectionChanged.emit()
        self._range_moved()

    @Slot()
    def clearRange(self):
        self._picks.range = None
        self.rangeChanged.emit()
        self.selectionChanged.emit()
        self._range_moved()

    @Slot(result="QVariantMap")
    def inspectSelection(self):
        """What an agent reads (`inspect_selection`): ids with kind, track, start, end, a line each; the range."""
        return selection.describe(self.doc, self._picks.ids, self._view["rows"], self._picks.range, self.label_of)

    def _follow_kit(self):
        """The kit's selection is the one list (anything may call its `selectMany`); the order, anchor and range
        here follow it (bridge.py connects this to selectionChanged)."""
        ids = list(self.selection)
        if ids != self._picks.ids:
            self._picks.set(ids, self._picks.anchor if self._picks.anchor in ids else None)
            self.picksChanged.emit()

    def _restore(self, change):
        """The person's undo / redo selects what the step touched again (so the next action is on the same things)."""
        if change is None or change.who != self.who or not (change.undoes or change.redoes):
            return
        kinds = ("note", "hit", "clip", "line", "track", "marker", "section", "sound")
        back = [i for i in dict.fromkeys(e.id for e in change.edits) if self.doc.has(i) and self.doc.item(i)["type"] in kinds]
        if back:
            self._pick(back)

    def _on_doc(self, event):
        """A selected item that went away (an undo of an add, a delete) leaves the selection; the rest stay."""
        if self._picks.keep(self.doc.has):
            self._pick(self._picks.ids)
        super()._on_doc(event)
        if event.kind == "change":
            self._restore(event.change)
