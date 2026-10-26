"""The bridge's selection and the rows it shows (a slot mix-in for DocBridge, see parts.py). One item, or several
(`selectMany`): the panel then shows the settings they all share (many.py), and an edit is one change on every one.
Selection, the More row and the rows' layout are screen state, not document changes. State: `self._kit` (kit_state.py).
"""
from __future__ import annotations

import time

import shiboken6

from PySide6.QtCore import Slot

from . import commands, many, pointer_quiet, row_memo, rows
from .after_frame import AfterFrame
from .history_rows import who_name
from .pending import finish_typing
from .parts import SlotMixin

_OWN: dict = {}         # (layout, kind) -> the layout with that kind's own rules (_static_of)
AHEAD_ROWS = 3          # settings rows made ahead per frame (~1.5-4 ms each: make_panels_ahead)


class SelectSlots(SlotMixin):
    @Slot(str)
    def select(self, item_id):
        """One item ("" = none)."""
        self.selectMany([item_id] if item_id else [])

    @Slot("QVariantList")
    def selectMany(self, ids):
        """Several items, the primary first (its name and order lead the panel); [] = none."""
        k = self._kit
        person = pointer_quiet.busy()       # asked first: the pick's own work below (200 outlines) outlasts QUIET_S
        ids, idx = list(dict.fromkeys(str(i) for i in ids)), self.doc.locs()
        gone = [i for i in ids if i not in idx]            # (one look per id: a whole song is thousands)
        if gone:
            return self._fail(f'Error: select: no item "{gone[0]}".')
        moved = ids != k.selection
        if moved:
            finish_typing()                 # a field's typing lands on the items it was typed for, before they change
            k.held = None
        k.selection, k.sel = ids, ids[0] if ids else ""
        kinds = dict.fromkeys(self.kinds_of(ids))           # each kind once, the first item's first
        reg = self.doc.kind.registry
        k.op_kind = (many.shared_op([reg.field_op(t) for t in kinds]) if ids else None,
                     next(iter(kinds)) if len(kinds) == 1 else "")
        k.static = self._layout()
        if moved:
            self.selectedItemsChanged.emit()
        if person:                          # a person's pick (pointer or key): its highlight and outline are drawn
            self._panel_later().ask(first=True)   # first, the panel in the frame after (after_frame.py); a reader of the rows
        else:                               # makes it now. A script's or an agent's: at once
            self._panel_later().due = False
            self._show_panel()

    def kinds_of(self, ids) -> list[str]:
        """Each id's item type, worked out once per selection and song data (the panel, its title, the count chip and
        the narrowing lines all ask; a whole-song selection is thousands of items). Read only."""
        key, kept = tuple(ids), self._kit.kinds
        if kept[0] is not self.doc.data or kept[1] != key:
            idx = self.doc.locs()
            kept = self._kit.kinds = (self.doc.data, key,       # (a gone id: doc.item says so)
                                      [idx[i].item["type"] if i in idx else self.doc.item(i)["type"] for i in key])
        return kept[2]

    def ready_new_kinds(self):
        """Every kind in the document that has no panel made ahead yet gets one, at idle: a kind present at open, and a
        kind that comes later (a person's new shape, a paste, an import, an agent's add). Its first pick found no page
        and made the whole panel in the frame after the click (~25-50 ms). Told after each document change (a frame
        later, never in the change's own frame); a kind already ready costs one pass over the items."""
        k, first = self._kit, {}
        for it in self.doc.items():
            kind = it["type"]
            if kind not in k.ready_kinds and kind not in first and (k.ahead_filter is None or k.ahead_filter(it)):
                first[kind] = it["id"]
        if first:
            k.ready_kinds.update(first)
            self.make_panels_ahead(list(first.values()))

    def _kinds_later(self) -> AfterFrame:
        if self._kit.kinds_job is None:
            self._kit.kinds_job = AfterFrame(self.ready_new_kinds, self, ahead=True)
        return self._kit.kinds_job

    def make_panels_ahead(self, ids):
        """The settings rows of these items' kinds, made ahead after the screen is drawn: each kind's page of the panel
        (row_pages.py), hidden, its rows parked (absent) a few per frame, so a later pick of that kind finds its rows
        waiting (model_pick.py). A kind's first panel made every row's control on the click that showed it (a first
        note drawn: ~20-30 ms; a group's first Ctrl+G or a kind's first pick in 2D: ~30-90 ms). Never in a click; a
        whole page at once held the screen ~30-60 ms, long enough to meet the next click."""
        steps, job = self._ahead_steps(ids), AfterFrame(None, self, ahead=True)

        def run():
            if not shiboken6.isValid(self.model):     # the window closed meanwhile (a new project, the layout check's
                return                              # next state): its panel is gone, nothing to make
            if pointer_quiet.busy() or next(steps, None) is not None:
                job.ask()                   # the next few rows after the next frame
        job._fn = run
        job.ask()

    def _ahead_steps(self, ids):
        for item_id in ids:
            rows = self._rows_of(item_id) or []
            shown = [r for r in rows if r.get("valid", True)]          # (a layout holds every setting; ~1 in 8 applies)
            for n in range(0, len(shown), AHEAD_ROWS):
                self.model.park(rows, shown[n:n + AHEAD_ROWS])
                yield True

    def _rows_of(self, item_id):
        """The rows a pick of this item alone would show, worked out with nothing sent (None: gone, or picked now)."""
        k = self._kit
        if not self.doc.has(item_id) or item_id in k.selection:
            return None
        was = (k.selection, k.sel, k.op_kind, k.static)
        try:
            kind = self.doc.item(item_id)["type"]
            k.selection, k.sel = [item_id], item_id
            k.op_kind = (many.shared_op([self.doc.kind.registry.field_op(kind)]), kind)
            k.static = self._layout()
            return self._rows()
        finally:
            k.selection, k.sel, k.op_kind, k.static = was

    def _panel_later(self) -> AfterFrame:
        if self._kit.panel is None:
            self._kit.panel = AfterFrame(self._show_panel, self)
        return self._kit.panel

    def _rows_due(self) -> AfterFrame:
        if self._kit.rows_due is None:
            self._kit.rows_due = AfterFrame(self._refresh, self)
        return self._kit.rows_due

    def _show_panel(self):
        """The selection's panel: its rows in place and at once (no reveal animation, and only the rows another kind
        adds or drops are made or freed), its name, then what follows the panel (panelShown: its actions, effects). A pick
        made inside a drag that holds the panel (Alt+drag's 200 copies: ~0.9 s of rows) shows it at the drop."""
        if self.holds_panel():
            self._kit.panel_held = True
            return
        self._kit.panel_held = False
        self._rows_due().cancel()           # (a change's rows still waiting: these are newer)
        self.model.update(self._rows(), instant=True)
        self.rowsChanged.emit()
        self._announce(force=True)
        self.panelShown.emit()

    def holds_panel(self) -> bool:
        """The app's say: a drag is moving many items now, so the panel follows at its drop (2D: drags.moving_many)."""
        return False

    def _panel_now(self):
        """A reader of the rows (or a change to them) right after a pick or a change: its panel first."""
        self._panel_later().flush()
        self._rows_due().flush()

    def _announce(self, force=False):
        """selectionChanged, when what the selection shows changed (or `force`): a document edit that leaves the
        name and kind alone (a drag, a typed value) re-sends nothing, so its listeners don't redo their work."""
        shown = self.selectedItem
        if force or shown != self._kit.shown_sel:
            self._kit.shown_sel = shown
            self.selectionChanged.emit()

    @Slot(result="QVariantList")
    def narrowLines(self):
        """Mixed kinds selected: a line per kind, [{kind, label: "3 layers", count}] (else []). Read it in a binding
        that also reads `selection`, so it follows the selection."""
        sel = self._kit.selection
        kinds = self.kinds_of(sel)
        if len(set(kinds)) < 2:                     # one kind: no lines
            return []
        last = {t: i for i, t in zip(sel, kinds)}   # each kind in words once (by_kind keeps a kind's last item's words)
        words = {t: self.kind_label(self.doc.item(i)) for t, i in last.items()}
        return many.by_kind([(t, words[t]) for t in kinds])

    @Slot(str)
    def narrowTo(self, kind):
        """Keep only the selected items of this kind (a narrowing line's click). A selection change, never a document
        change: no undo step."""
        keep = [i for i in self._kit.selection if self.doc.item(i)["type"] == kind]
        if keep:
            self.selectMany(keep)

    @Slot(result="QVariantMap")
    def lastChanged(self):
        """{who, ago, label, session}: who changed the selection last, when, and what they did ({} = nothing yet).
        Read it in a binding that also reads `historyCount` and `selection`."""
        c = many.last_change(self.doc, self._kit.selection)
        if c is None:
            return {}
        return {"who": who_name(c.who, self.who), "ago": many.ago(c.t, time.time()) if c.t else "", "label": c.label,
                "session": c.session or ""}

    @Slot()
    def toggleMore(self):
        self._kit.more = not self._kit.more
        self._refresh()
        self._announce(force=True)

    def shown(self):
        """(on screen, behind More): param names for the selection, in screen order."""
        self._panel_now()
        return rows.shown(self.model.rows)

    def _items(self):
        return [i for i in self.doc.items() if i["id"] != self.doc.data["id"]]

    def _first(self):
        return next((i["id"] for i in self._items()), "")

    def _commands(self):
        sel = list(self._kit.selection)
        return (commands.build(self.doc, sel, self.label_of, self.kind_label, self.selection_label(sel) if sel else "")
                + self.extra_commands())

    def _rows(self):
        """The selection's rows: one item's own, or many items' folded into one panel (row_memo.fold: alike items
        compared column by column). Each item's rows are kept between picks and patched after a change (row_memo)."""
        k = self._kit
        if len(k.evaluated) > len(k.selection):           # kept for the items these rows are of, never one picked before
            k.evaluated = {i: k.evaluated[i] for i in k.selection if i in k.evaluated}
        if k.stepping or not k.selection:
            each = [self._item_rows(self.doc.item(i)) for i in k.selection]
            return [] if not each else each[0] if len(each) == 1 else many.merge(each)
        entries = [self._entry(self.doc.item(i)) for i in k.selection]
        return entries[0].rows if len(entries) == 1 else row_memo.fold(entries, many.merge)

    def _entry(self, it) -> row_memo.Entry:
        """The item's kept rows (row_memo), else borrowed from an alike item's (row_memo.borrow: a Ctrl+A over 200
        layers after an add worked out every one, ~2 ms each), else worked out now; kept."""
        k = self._kit
        opened = k.open_groups
        stamp = (self._static_of(it), k.more, k.search,
                 tuple(sorted(opened.items())) if isinstance(opened, dict) else tuple(sorted(opened)), self.rows_context())
        e = k.memo.get(it["id"], it, stamp, self.facts_of, self._redo_rows)
        if e is None:
            facts, place = self.facts_of(it), (it["type"], self.doc.locs()[it["id"]].parent)
            e = self._borrowed(it, stamp, place, facts)
            if e is None:
                seen = {}
                return k.memo.put(it["id"], it, stamp, facts, seen, self._item_rows(it, facts, seen), place)
        k.evaluated[it["id"]] = (self.doc.data, k.static, e.rows)
        return e

    def _borrowed(self, it, stamp, place, facts):
        """The item's rows borrowed from an alike item's kept ones (row_memo.borrow), or None."""
        shown, starts, gone = self.shown_values(it), self.starts(it), frozenset(self.on_page(it))
        return self._kit.memo.borrow(it["id"], it, stamp, place, facts, shown, starts, gone,
                                     lambda item, old: self._redo_rows(item, old, (shown, starts, gone)),
                                     lambda name: self.list_choices(it, name))

    def _redo_rows(self, it, old, known=None):
        """These rows of the item with their values, key marks and expressions read again (row_memo's patch):
        (new rows, the values shown, starts, the key-mark reader, the fields shown elsewhere on the page). `known`:
        (shown, starts, gone) of the item, already read."""
        shown, starts, gone = known or (self.shown_values(it), self.starts(it), frozenset(self.on_page(it)))
        anim, expr = (lambda name: self.anim_state(it, name)), (lambda name: self.expr_state(it, name))
        new = [rows._values({**r}, shown, anim, expr, None, {}) for r in old]        # (no list or pick: row_memo)
        return new, shown, starts, anim, gone

    def rows_context(self):
        """What an item's rows read besides the document and the panel's own state, which no change announces (2D: the
        playhead, the markers): kept rows are worked out again when it differs. None: nothing."""
        return None

    def _item_rows(self, it, facts=None, seen=None):
        k = self._kit
        static = self._static_of(it)
        step, kept = bool(k.stepping), self._kept_rows(it["id"])
        gone = self.on_page(it)
        if facts is None:
            facts = {} if step else self.facts_of(it)
        shown, starts = self.shown_values(it), {} if step else self.starts(it)
        evaluated = rows.evaluate(static, shown, facts, k.more,
                                  lambda name: self.anim_state(it, name), lambda name: self.expr_state(it, name),
                                  lambda name: self.list_choices(it, name), k.open_groups, k.search, gone,
                                  starts, step=step, kept=kept, seen=seen)
        k.evaluated[it["id"]] = (self.doc.data, k.static, evaluated)       # (what later steps keep: no copy)
        if seen is not None:
            seen["gone"], seen["shown"], seen["starts"] = frozenset(gone), shown, starts
        return rows.omit(evaluated, gone)

    def _static_of(self, it):
        """The layout this item's rows are worked out from: the selection's, with the item's own rules when kinds are
        mixed (many.own_rules), made once per layout and kind."""
        k = self._kit
        if k.op_kind[1]:
            return k.static
        op = self.doc.kind.registry.field_op(it["type"])
        key = (id(k.static), it["type"])
        got = _OWN.get(key)
        if got is None or got[0] is not k.static or got[1] is not op:
            if len(_OWN) > 64:
                _OWN.clear()
            got = _OWN[key] = (k.static, op, many.own_rules(k.static, op))
        return got[2]

    def _kept_rows(self, item_id):
        """A drag's step: the item's rows the steps since the rows last followed left alone, as they were then
        ({param row id: its row}); None: every row is read (not a step, or what the steps touched can't be told)."""
        k = self._kit
        was = k.evaluated.get(item_id)
        if not k.stepping or was is None or k.stepping[1] is None or was[0] is not k.stepping[0] or was[1] is not k.static:
            return None
        fields = k.stepping[1].fields_of(self.doc, item_id)
        return None if fields is None else {r["id"]: r for r in was[2] if r["row"] == "param" and r["id"] not in fields}

    def _refresh(self):
        """The same rows with new values or validity: changed in place, so each row animates its own reveal."""
        if self._panel_later().due:         # a pick's panel not shown yet: shown now, as a pick shows it
            return self._panel_later().flush()
        if self._kit.panel_held:            # (or held by the drag that just ended)
            return self._show_panel()
        self._rows_due().cancel()
        self.model.update(self._rows())
        self.rowsChanged.emit()

    HELD = ("valid", "holds", "open", "names")         # what a drag's step leaves as it was (_step_rows)

    def _step_rows(self):
        """A drag's step: the shown rows' values follow it; which rows show and which groups are open stay as at the
        press until the drop (a row appearing mid-drag makes its control then: tens of ms in one pointer move)."""
        self._panel_now()
        old = self.model.rows
        k = self._kit                       # values only: the rows' HELD keys come from the press (rows.evaluate
        k.stepping, k.stepped = k.stepped or (None, None), None     # step), and only those of the fields stepped
        try:
            new = self._rows()
        finally:
            k.stepping = False
        if [r["id"] for r in new] == [r["id"] for r in old]:
            self.model.update([{**n, **{h: o[h] for h in self.HELD if h in o}} for n, o in zip(new, old)])

    def _follow_doc(self, step=False):
        """After a document change: a selected item that went away (e.g. undo of an add) leaves the selection. `step`:
        a drag's step: the rows follow at most once per screen refresh (news.OnceAFrame), the drag's end in full."""
        sel = self._kit.selection
        if not step and self._kit.ready_kinds:      # (from the window's own first pass on: session.py)
            self._kinds_later().ask()
        if any(not self.doc.has(i) for i in sel):
            kept = [i for i in sel if self.doc.has(i)]
            self.selectMany(kept) if len(kept) > 1 else self.select(kept[0] if kept else self._first())
        elif not self.reached(sel):                        # a change elsewhere leaves these rows as they are
            return
        elif step:
            if len(sel) == 1:            # many items dragged together: their folded rows show mixed values anyway, and
                self._kit.paced.ask()    # folding 200 items' rows each step cost ~70 ms; they follow at the drop
        else:
            self._kit.paced.cancel()
            self._rows_due().ask()          # the rows' new values the frame after: an action that then picks what it
            self._announce()                # made (Ctrl+G) never builds the old selection's rows (~9 ms)                               # only if its name or kind changed (an agent's rename)
