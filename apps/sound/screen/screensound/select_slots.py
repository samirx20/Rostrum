"""The bridge's selection as a list, the time range, and the one action list (a slot mix-in for SoundBridge, see
gui-kit parts.py). Click / Ctrl+click / Shift+click / box / Ctrl+A / Esc pick ids (selection.py); what is done with
them is action_slots.py (the one action list). Selecting is screen state, not
an undo step; every action is one change. The whole list goes to the kit's `selectMany` (H28: the settings panel
shows what the selected items share); the order picked, the Shift anchor and the time range stay here. After the
person's undo / redo, what that step touched is selected again (read from the change's `undoes` / `redoes`).
"""
from __future__ import annotations

import itertools
from contextlib import contextmanager

from PySide6.QtCore import Property, QTimer, Signal, Slot
from PySide6.QtQml import qjsEngine
from rostrum_core import edits as E
from rostrum_gui import pointer_quiet

from . import clipboard, selection, timing

BLOCKS = ("note", "hit", "clip")     # drawn on the lanes and in the roll (`picked`), never as a control of their own
SETTLE_MS = 40      # a press's outline and first moves are drawn before the settings panel is made (_settle)
_STAMPS = itertools.count(1)    # pickStamp: one count for every bridge (Picks.js keeps its maps across a reopen)


class SelectSlots:
    rangeChanged = Signal()
    picksChanged = Signal()
    pickRowsChanged = Signal()
    areaChanged = Signal()

    @property
    def _picks(self) -> selection.Selection:
        if "_picks_" not in self.__dict__:
            self.__dict__["_picks_"] = selection.Selection()
            self.__dict__["_area"] = "arrange"
        return self.__dict__["_picks_"]

    @property
    def _board(self) -> dict:
        """What Ctrl+C kept: one clipboard for the whole app run, so a copy pastes into another song too."""
        return clipboard.kept()

    @_board.setter
    def _board(self, board):
        clipboard.keep(board)

    # ---- reads for QML --------------------------------------------------------------------------------------
    @Property("QVariantList", notify=picksChanged)
    def selectedIds(self):
        return list(self._picks.ids)

    @Property("QVariant", notify=picksChanged)
    def picked(self):
        """id -> true for every selected id. Made into one script object once per selection, but each QML reader still
        gets a copy of it (~2.5 ms each with 3,607 picked): the painted surfaces read Picks.js instead (`pickStamp`,
        `pickRows`: one shared object per row). Headers read the small `pickedHeads`."""
        kept = self._picked_maps()
        if kept[1] is None:                 # made on the first read (the Editor's roll): no other surface reads it
            js, plain = qjsEngine(self), dict.fromkeys(kept[0], True)
            kept[1] = js.toScriptValue(plain) if js is not None else plain
        return kept[1]

    @Property("QVariantMap", notify=picksChanged)
    def pickedHeads(self):
        """`picked` without notes, hits and clips: what a track's header, a marker, a section or a line reads (a few
        ids: ~30 headers each reading 3,352 picks cost ~100 ms of Ctrl+A)."""
        return self._picked_maps()[2]

    def _picked_maps(self):
        """[ids, picked, pickedHeads], made once per selection (`picked` on its first read: `picked`). The list is
        known by itself first (Selection makes a new one on every change, never edits one in place): ~55 readers each
        copying and comparing 3,607 ids cost ~10 ms of every whole-song pick."""
        ids = self._picks.ids
        kept = self.__dict__.get("_picked_maps_")
        if kept is not None and kept[0] is not ids and kept[0] == ids:
            kept[0] = ids                   # the same ids again: the same shared objects
        if kept is None or kept[0] is not ids:
            idx = self.doc.locs()
            heads = {i: True for i in ids if i in idx and idx[i].item["type"] not in BLOCKS}
            kept = self.__dict__["_picked_maps_"] = [ids, None, heads]
        return kept

    @Property(int, notify=pickRowsChanged)
    def pickStamp(self):
        """A new number whenever the selection, or which row holds which pick, changes: the lanes' and the velocity
        strip's bindings name it and read their picks from Picks.js (one shared script object per row)."""
        return self.__dict__.get("_pick_stamp", 0)

    @Slot(result="QVariantMap")
    def pickRows(self):
        """The selection by arrangement row: {row id: [ids drawn in that row]} (Picks.js, once per pickStamp)."""
        return self._pick_rows()[2]

    def _pick_rows(self):
        """(ids, rows, by row), made once per selection and rows. A block is in each row that draws it (a folded
        group's header and its track)."""
        ids, rows = self._picks.ids, (self._view or {}).get("rows") or []
        kept = self.__dict__.get("_pick_rows_")
        if kept is not None and kept[0] is ids and kept[1] is rows:
            return kept
        index = self.__dict__.get("_row_index_")
        if index is None or index[0] is not rows:
            at: dict = {}
            for r in rows:
                for b in r.get("blocks", ()):
                    at.setdefault(b["id"], []).append(r["id"])
            index = self.__dict__["_row_index_"] = (rows, at)
        by: dict = {}
        at = index[1]
        for i in ids:
            for r in at.get(i, ()):
                by.setdefault(r, []).append(i)
        kept = self.__dict__["_pick_rows_"] = (ids, rows, by)
        return kept

    def _picks_changed(self):
        """Every reader of the selection told: the stamp first (the lanes read their rows' picks by it)."""
        if "_rows_check" in self.__dict__:
            self.__dict__["_rows_check"] = False        # (the lanes read their picks anew: `_picks_after`)
        self.__dict__["_pick_stamp"] = next(_STAMPS)
        self.pickRowsChanged.emit()
        self.picksChanged.emit()

    def _rows_sent(self):
        """New rows went to the screen (rows_view._send_rows): when they hold the selected blocks in other rows than
        before (Ctrl+Up moved the notes to the track above, a block added that is selected), the lanes read their picks
        again. The selection itself is the same: nothing else is told."""
        if not self._picks.ids:
            return
        if "_rows_check" in self.__dict__:              # a change that may pick what it made: checked at its end
            self.__dict__["_rows_check"] = True
            return
        was = self.__dict__.get("_pick_rows_")
        if was is not None and was[0] is self._picks.ids and self._pick_rows()[2] == was[2]:
            return
        self.__dict__["_pick_stamp"] = next(_STAMPS)
        self.pickRowsChanged.emit()

    @contextmanager
    def _picks_after(self):
        """A change that picks what it touched or made once its rows are sent (Ctrl+D, an undo, a redo): the rows'
        check of the old selection (`_rows_sent`) waits for its end and is dropped when a new selection came meanwhile
        (every lane reads its picks then anyway): a whole-song Ctrl+D or redo looked 3,607 picks up among 7,214 blocks
        for a selection about to go."""
        if "_rows_check" in self.__dict__:
            yield
            return
        self.__dict__["_rows_check"] = False
        try:
            yield
        finally:
            due = self.__dict__.pop("_rows_check", False)
        if due:
            self._rows_sent()

    @Property(str, notify=picksChanged)
    def selectionWords(self):
        """The count chip: "5 notes", "2 tracks" ("" for none)."""
        return selection.count_words(self._kinds())

    def selection_label(self, ids):
        """The kit's panel title and Ctrl K hints: one item's name, else Sound's count words ("5 notes")."""
        if len(ids) == 1:
            return super().selection_label(ids)
        return selection.count_words(self.kinds_of(ids))

    def _kinds(self):
        return self.kinds_of(self._picks.ids)

    # ---- picking ----------------------------------------------------------------------------------------------
    @Slot(str)
    def select(self, item_id):
        """One item alone ("" = none)."""
        self._pick([item_id] if item_id else [])

    @Slot(str)
    def pressSelect(self, item_id):
        """A press on an item in the arrangement or the Editor: it alone, its outline at once; the settings panel and
        the Editor's track follow a moment later, or when the drag the press starts ends (`_settle`)."""
        self._pick([item_id] if item_id else [], later=True)
        self._settle()

    @Slot("QVariantList")
    def pickMany(self, ids):
        """Several ids at once ([] = none; an empty click): the outline at once, the kit's `selectMany` (the settings
        panel) once the pointer is quiet (`_settle`)."""
        self._pick([str(i) for i in ids], later=True)
        self._settle()

    def _pick(self, ids, anchor=None, later=False, checked=False):
        """`later`, or a drag open (a press on an item, a drawn note): the outline shows at once, the settings panel
        and the Editor's track follow when the drag ends (`_settle`): making the panel's rows costs frames the press
        must not wait for. `checked`: the caller has just found every id in the song (one look per id per pick: a
        whole-song undo looked each of 3,607 ids up ~6 times)."""
        if not checked:
            idx = self.doc.locs()
            gone = [i for i in ids if i not in idx]
            if gone:
                return self._fail(f'Error: select: no item "{gone[0]}".')
        was = list(self._picks.ids)
        self._picks.set(ids, anchor)
        if ids:
            self.__dict__["_range_newer"] = False        # items picked after the range: actions mean them (Facts)
        if later or self._drag is not None:
            self.__dict__["_unsettled"] = True
            self._rows_due().cancel()       # a change's rows for the old selection: the settled pick shows the panel anew
        else:
            self.__dict__["_unsettled"] = False
            self.selectMany(self._picks.ids)          # the kit: the settings panel + selectionChanged
        if self._picks.ids != was:
            self._picks_changed()
        elif not self.__dict__["_unsettled"] and "_hub" in self.__dict__:      # the same items settling: the outlines
            self._hub.refresh_later()       # are drawn; the actions follow a frame after the panel (a second picksChanged
                                            # converted and compared 3,352 outlines in every lane for nothing)

    def _settle(self):
        """A press or a drag that picked has ended: the kit's selection (the settings panel, the Editor's track)
        follows once, after the press or the drop is drawn."""
        if self.__dict__.get("_unsettled"):
            QTimer.singleShot(SETTLE_MS, self, self._settled)

    def _settled(self):
        if pointer_quiet.busy():                 # the person is still clicking or dragging: the panel waits for a quiet
            return QTimer.singleShot(SETTLE_MS, self, self._settled)    # pointer, never inside a click (M4)
        if self.__dict__.get("_unsettled") and self._drag is None and self._kit.scrub is None:
            idx = self.doc.locs()
            self._pick([i for i in self._picks.ids if i in idx], self._picks.anchor, checked=True)

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
        if p.ids == [item_id] and self.__dict__.get("_unsettled"):
            return self._settle()                   # the release of a press that picked it: the panel is on its way
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
        """A box's move: the outlines follow at once; the settings panel and the Editor's track once it ends (endBox):
        making the panel's rows for each move cost 20-120 ms a move on a 31-s song (M4). Its first move remembers the
        selection as it was (cancelBox gives it back)."""
        was = self.__dict__.setdefault("_box_was", (list(self._picks.ids), self._picks.anchor))
        base = self.__dict__.setdefault("_box_base", list(was[0]) if add else [])
        ids = [*base, *got] if add else got
        if ids != self._picks.ids:
            self._pick(ids, later=True)

    @Slot()
    def endBox(self):
        self.__dict__.pop("_box_base", None)
        self.__dict__.pop("_box_was", None)
        self._settle()

    @Slot()
    def cancelBox(self):
        """Esc while a box is drawn: the selection exactly as before the box began (the same items, in order, the same
        anchor for Shift), and the box ends. Nothing to undo: a selection is not a change."""
        was = self.__dict__.pop("_box_was", None)
        self.__dict__.pop("_box_base", None)
        if was is not None:
            idx = self.doc.locs()                   # (an agent may have removed one meanwhile)
            self._pick([i for i in was[0] if i in idx], was[1] if was[1] in idx else None, later=True, checked=True)
        self._settle()

    @Slot(str)
    def focusArea(self, area):
        """The area last clicked ("arrange" or "roll"): Ctrl+A takes everything of its kind there; its action bar
        shows."""
        if area != self._area:
            self._area = area
            self.areaChanged.emit()            # not a new selection: a name field being typed in keeps its keys

    @Property(str, notify=areaChanged)
    def area(self):
        return self._area

    @Slot(str)
    def focusTrack(self, track_id):
        """A click on empty lane space: that track is the one the Editor shows and Paste goes to (not a selection)."""
        if self.doc.has(track_id) and track_id != self._track:
            self._track = track_id
            self._show_roll()

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
        """Ctrl+A: the outlines at once, the settings panel and the actions once they are drawn (`_settle`)."""
        if self._area == "roll":
            ids = [b["id"] for b in self._view["roll"]["blocks"]]
        else:
            tracks = [i for i in self._picks.ids if self.doc.item(i)["type"] == "track"] or \
                [r["id"] for r in self._view["rows"]]
            ids = [b["id"] for r in self._view["rows"] if r["id"] in tracks for b in r["blocks"]]
        self._pick(ids, later=True)
        self._settle()

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

    @Slot(float, float, bool, float)
    def setRange(self, t0, t1, free, per_sec=0.0):
        """A drag on the ruler: a time range, each edge by the one rule (timing.snap): a bar or beat line within a few
        pixels of the pointer, else the nearest grid line; exact when free (Ctrl, the seconds scale). `per_sec`: the
        ruler's pixels per second."""
        self._set_range(t0, t1, free, True, 1.0 / per_sec if per_sec > 0 else 0.0)

    def _set_range(self, t0, t1, free, drawn, px=0.0):
        """`drawn`: a person drew it, so Ctrl+D etc. mean the range. The loop button's own range (drawn False) is only where
        the loop plays: the selected items' actions stay first in the panel."""
        t0, t1 = sorted((t0, t1))
        root, grid = self.doc.data, self._grid_now
        a, b = timing.snap(t0, root, free, grid, px=px), timing.snap(t1, root, free, grid, px=px)
        self._picks.range = (a, b) if b - a > 1e-3 else None
        if drawn:
            self.__dict__["_range_newer"] = True         # a range drawn after the items: Ctrl+D etc. mean the range
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
        here follow it (bridge.py connects this to selectedItemsChanged)."""
        ids = list(self.selection)
        if ids != self._picks.ids:
            self._picks.set(ids, self._picks.anchor if self._picks.anchor in ids else None)
            self._picks_changed()

    def _restore(self, change):
        """The person's undo / redo selects what the step touched again (so the next action is on the same things)."""
        if change is None or change.who != self.who or not (change.undoes or change.redoes):
            return
        kinds = ("note", "hit", "clip", "line", "track", "marker", "section")
        touched = list(dict.fromkeys(i for e in change.edits for i in E.ids(e)))
        # what the original step acted on, when its calls name it (a track moved down also shifts the one it passed:
        # only the moved one is selected again, as before the move)
        h = self.doc.history
        aimed = dict.fromkeys(t for seq in (change.undoes or change.redoes) if 0 < seq <= len(h.changes)
                              for c in h.get(seq).calls for t in (c.get("target") or []))     # (in the calls' order: a
        # set's order scrambled a whole-song selection, so the next Ctrl+D made its copies out of order and every lane
        # was sent them whole: ~2x the first Ctrl+D)
        touched = [i for i in touched if i in aimed] or touched      # a call aimed at a track that made notes: the notes
        idx = self.doc.locs()
        back = [i for i in touched if i in idx and idx[i].item["type"] in kinds]
        if not back:                # the step only made things (undo of a duplicate): what it was aimed at, like a Repeat's
            back = [t for t in aimed if t in idx and idx[t].item["type"] in kinds]
        if set(back) == set(self._picks.ids):       # already what is selected (undo of a whole-song Right): picking it
            return                                  # again in the step's order redrew 3,352 outlines in every lane
        if back:                    # the outlines now; the settings panel once the undo is drawn (`_settle`)
            self._pick(back, later=True, checked=True)
            self._settle()

    def _on_doc(self, event):
        """A selected item that went away (an undo of an add, a delete) leaves the selection; the rest stay."""
        if self._picks.keep(self.doc.locs().__contains__):
            self._pick(self._picks.ids, later=True, checked=True)      # the panel follows after the change is drawn
            self._settle()
        super()._on_doc(event)      # (the person's undo / redo picks what it touched once the rows are sent: _restore,
                                    # from bridge.py; picked first, every lane looked for 3,607 picks among its old blocks)
