"""The bridge's selection and the rows it shows (a slot mix-in for DocBridge, see parts.py). One item, or several
(`selectMany`): the panel then shows the settings they all share (many.py), and an edit is one change on every one.
Selection, the More row and the rows' layout are screen state, not document changes. State: `self._kit` (kit_state.py).
"""
from __future__ import annotations

import time

from PySide6.QtCore import Slot

from . import commands, many, pointer_quiet, rows
from .after_frame import AfterFrame
from .history_rows import who_name
from .pending import finish_typing
from .parts import SlotMixin


class SelectSlots(SlotMixin):
    @Slot(str)
    def select(self, item_id):
        """One item ("" = none)."""
        self.selectMany([item_id] if item_id else [])

    @Slot("QVariantList")
    def selectMany(self, ids):
        """Several items, the primary first (its name and order lead the panel); [] = none."""
        k = self._kit
        ids = list(dict.fromkeys(str(i) for i in ids))
        gone = [i for i in ids if not self.doc.has(i)]
        if gone:
            return self._fail(f'Error: select: no item "{gone[0]}".')
        moved = ids != k.selection
        if moved:
            finish_typing()                 # a field's typing lands on the items it was typed for, before they change
            k.held = None
        k.selection, k.sel = ids, ids[0] if ids else ""
        kinds = [self.doc.item(i)["type"] for i in ids]
        reg = self.doc.kind.registry
        k.op_kind = (many.shared_op([reg.field_op(t) for t in kinds]) if ids else None,
                     kinds[0] if len(set(kinds)) == 1 else "")
        k.static = self._layout()
        if moved:
            self.selectedItemsChanged.emit()
        if pointer_quiet.busy():            # a pointer's pick: its highlight and outline (selectedItemsChanged) are
            self._panel_later().ask()       # drawn first, the panel in the frame after (after_frame.py)
        else:
            self._panel_later().due = False
            self._show_panel()

    def _panel_later(self) -> AfterFrame:
        if self._kit.panel is None:
            self._kit.panel = AfterFrame(self._show_panel, self)
        return self._kit.panel

    def _show_panel(self):
        """The selection's panel: its rows in place and at once (no reveal animation, and only the rows another kind
        adds or drops are made or freed), its name, then what follows the panel (panelShown: its actions, effects)."""
        self.model.update(self._rows(), instant=True)
        self.rowsChanged.emit()
        self._announce(force=True)
        self.panelShown.emit()

    def _panel_now(self):
        """A reader of the rows (or a change to them) right after a pointer's pick: the pick's panel first."""
        self._panel_later().flush()

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
        k = self._kit
        return many.by_kind([(it["type"], self.kind_label(it)) for it in map(self.doc.item, k.selection)])

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
        each = [self._item_rows(self.doc.item(i)) for i in self._kit.selection]
        return [] if not each else each[0] if len(each) == 1 else many.merge(each)

    def _item_rows(self, it):
        k = self._kit
        static = k.static if k.op_kind[1] else many.own_rules(k.static, self.doc.kind.registry.field_op(it["type"]))
        evaluated = rows.evaluate(static, self.shown_values(it), self.facts_of(it), k.more,
                                  lambda name: self.anim_state(it, name), lambda name: self.expr_state(it, name),
                                  lambda name: self.list_choices(it, name), k.open_groups, k.search, self.on_page(it),
                                  self.starts(it))
        return rows.omit(evaluated, self.on_page(it))

    def _refresh(self):
        """The same rows with new values or validity: changed in place, so each row animates its own reveal."""
        if self._panel_later().due:         # a pick's panel not shown yet: shown now, as a pick shows it
            return self._panel_later().flush()
        self.model.update(self._rows())
        self.rowsChanged.emit()

    HELD = ("valid", "holds", "open", "names")         # what a drag's step leaves as it was (_step_rows)

    def _step_rows(self):
        """A drag's step: the shown rows' values follow it; which rows show and which groups are open stay as at the
        press until the drop (a row appearing mid-drag makes its control then: tens of ms in one pointer move)."""
        self._panel_now()
        new, old = self._rows(), self.model.rows
        if [r["id"] for r in new] == [r["id"] for r in old]:
            self.model.update([{**n, **{k: o[k] for k in self.HELD if k in o}} for n, o in zip(new, old)])

    def _follow_doc(self, step=False):
        """After a document change: a selected item that went away (e.g. undo of an add) leaves the selection. `step`:
        a drag's step: the rows follow at most once per screen refresh (news.OnceAFrame), the drag's end in full."""
        sel = self._kit.selection
        if any(not self.doc.has(i) for i in sel):
            kept = [i for i in sel if self.doc.has(i)]
            self.selectMany(kept) if len(kept) > 1 else self.select(kept[0] if kept else self._first())
        elif not self.reached(sel):                        # a change elsewhere leaves these rows as they are
            return
        elif step:
            self._kit.paced.ask()
        else:
            self._kit.paced.cancel()
            self._refresh()
            self._announce()                               # only if its name or kind changed (an agent's rename)
