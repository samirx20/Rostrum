"""The bridge's selection and the rows it shows (a slot mix-in for DocBridge, see parts.py). One item, or several
(`selectMany`): the panel then shows the settings they all share (many.py), and an edit is one change on every one.
Selection, the More row and the rows' layout are screen state, not document changes. State: `self._kit` (kit_state.py).
"""
from __future__ import annotations

import time

from PySide6.QtCore import Slot

from . import commands, many, rows
from .history_rows import who_name
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
        k.selection, k.sel = ids, ids[0] if ids else ""
        kinds = [self.doc.item(i)["type"] for i in ids]
        reg = self.doc.kind.registry
        k.op_kind = (many.shared_op([reg.field_op(t) for t in kinds]) if ids else None,
                     kinds[0] if len(set(kinds)) == 1 else "")
        k.static = self._layout()
        self.model.reset(self._rows())      # a new selection swaps the list at once (no reveal animation)
        self.rowsChanged.emit()
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
        self.selectionChanged.emit()

    def shown(self):
        """(on screen, behind More): param names for the selection, in screen order."""
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
        evaluated = rows.evaluate(static, self.shown_values(it), self.doc.kind.facts(it, self.doc), k.more,
                                  lambda name: self.anim_state(it, name), lambda name: self.expr_state(it, name),
                                  lambda name: self.list_choices(it, name), k.open_groups, k.search)
        return rows.omit(evaluated, self.on_page(it))

    def _refresh(self):
        """The same rows with new values or validity: changed in place, so each row animates its own reveal."""
        self.model.update(self._rows())
        self.rowsChanged.emit()

    def _follow_doc(self):
        """After a document change: a selected item that went away (e.g. undo of an add) leaves the selection."""
        sel = self._kit.selection
        if any(not self.doc.has(i) for i in sel):
            kept = [i for i in sel if self.doc.has(i)]
            self.selectMany(kept) if len(kept) > 1 else self.select(kept[0] if kept else self._first())
        else:
            self._refresh()
            self.selectionChanged.emit()                   # its name may have changed (an agent's rename)
