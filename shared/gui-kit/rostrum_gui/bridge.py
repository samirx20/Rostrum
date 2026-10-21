"""The document bridge: what QML sees of one rostrum_core Document, and the only way QML changes it.

Every edit is an operation through doc.apply (a scrub through doc.gesture: one change for the whole drag),
recorded with the person's name, so undo, history and "who changed what" work the same as for agents.
The bridge listens to the document (doc.subscribe), so an agent's or script's change shows up in place too.
Selection and the More row are screen state, not document changes. A refused edit fails loudly: the error
line goes to the console and to `status` (the top bar shows it in red).
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import RostrumError, Who

from . import commands, rows
from .edits import Scrub, edit_label, field_call
from .model import RowsModel


def name_of(item: dict) -> str:
    return str(item.get("name") or item["id"])


class DocBridge(QObject):
    selectionChanged = Signal()
    docChanged = Signal()
    statusChanged = Signal()

    def __init__(self, doc, who=None, parent=None):
        super().__init__(parent)
        self.doc, self.who = doc, who or Who.person("sam")
        self._sel, self._more, self._status = "", False, ""
        self._scrub: Scrub | None = None
        self._static: list[dict] = []
        self.model = RowsModel(rows.ROLES, self)
        self._unsubscribe = doc.subscribe(self._on_doc)
        self.select(self._first())

    # ---- reads for QML ----------------------------------------------------------------------------------------
    @Property(str, notify=selectionChanged)
    def selected(self):
        return self._sel

    @Property("QVariantMap", notify=selectionChanged)
    def selectedItem(self):
        if not self._sel:
            return {"id": "", "label": "", "kind": ""}
        it = self.doc.item(self._sel)
        return {"id": it["id"], "label": name_of(it), "kind": it["type"]}

    @Property("QVariantList", notify=docChanged)
    def items(self):
        return [{"id": i["id"], "label": name_of(i), "kind": i["type"]} for i in self._items()]

    @Property(QObject, constant=True)
    def rows(self):
        return self.model

    @Property(bool, notify=selectionChanged)
    def moreOpen(self):
        return self._more

    @Property(int, notify=docChanged)
    def historyCount(self):
        return len(self.doc.history.changes)

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    def shown(self):
        """(on screen, behind More): param names for the selected item, in screen order."""
        return rows.shown(self.model.rows)

    # ---- screen state ---------------------------------------------------------------------------------------
    @Slot(str)
    def select(self, item_id):
        if item_id and not self.doc.has(item_id):
            return self._fail(f'Error: select: no item "{item_id}".')
        self._sel = item_id
        op = self.doc.kind.registry.field_op(self.doc.item(item_id)["type"]) if item_id else None
        self._static = rows.layout(op)
        self.model.reset(self._rows())      # a new selection swaps the list at once (no reveal animation)
        self.selectionChanged.emit()

    @Slot()
    def toggleMore(self):
        self._more = not self._more
        self.model.update(self._rows())
        self.selectionChanged.emit()

    # ---- edits: every one an operation ------------------------------------------------------------------------
    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        """One inspector edit = one change (quick repeats of the same field merge: the core's nudge)."""
        return self._guard(lambda: self._apply([field_call(self.doc, self._sel, param, value)],
                                               edit_label(self.doc, self._sel, param, value)))

    @Slot(str)
    def beginScrub(self, param):
        self.endScrub()
        def go():
            self._scrub = Scrub(self.doc, self.who, self._sel, param)
        self._guard(go)

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        if self._scrub is None or self._scrub.name != param:
            self.beginScrub(param)
        if self._scrub is not None:
            self._guard(lambda: self._scrub.preview(value))

    @Slot()
    def endScrub(self):
        self._close_scrub(cancel=False)

    @Slot()
    def cancelScrub(self):
        self._close_scrub(cancel=True)

    @Slot(str, result="QVariantList")
    def commands(self, query):
        return [{k: c[k] for k in ("key", "label", "hint")} for c in commands.search(self._commands(), query)]

    @Slot(str, result=bool)
    def run(self, key):
        """Run a command-bar command by key: its calls as one change (or a selection)."""
        cmd = next((c for c in self._commands() if c["key"] == key), None)
        if cmd is None:
            self._fail(f'Error: command bar: "{key}" is not available right now.')
            return False
        if "select" in cmd:
            self.select(cmd["select"])
            return True
        return self._guard(lambda: self._apply(cmd["calls"], cmd["label"]))

    @Slot()
    def undo(self):
        self._guard(lambda: self._done(self.doc.undo(self.who), "Nothing to undo"))

    @Slot()
    def redo(self):
        self._guard(lambda: self._done(self.doc.redo(self.who), "Nothing to redo"))

    # ---- inside ---------------------------------------------------------------------------------------------
    def _items(self):
        return [i for i in self.doc.items() if i["id"] != self.doc.data["id"]]

    def _first(self):
        return next((i["id"] for i in self._items()), "")

    def _commands(self):
        return commands.build(self.doc, [self._sel] if self._sel else [], name_of)

    def _apply(self, calls, label):
        self._done(self.doc.apply(calls, self.who, label=label), "")

    def _close_scrub(self, cancel):
        s, self._scrub = self._scrub, None
        if s is not None:
            self._guard(lambda: self._done(s.end(cancel), ""))

    def _done(self, change, nothing):
        self._set_status(change.label if change is not None else nothing)

    def _guard(self, fn) -> bool:
        """Run an edit; a refusal is reported (console + status), never swallowed, never a crash."""
        try:
            fn()
            return True
        except RostrumError as e:
            self._fail(e.line())
            return False

    def _rows(self):
        if not self._sel:
            return []
        it = self.doc.item(self._sel)
        return rows.evaluate(self._static, it, self.doc.kind.facts(it), self._more)

    def _on_doc(self, event):
        if self._sel and not self.doc.has(self._sel):      # the selected item went away (e.g. undo of an add)
            self.select(self._first())
        else:
            self.model.update(self._rows())
        self.docChanged.emit()

    def _set_status(self, text):
        self._status = text
        self.statusChanged.emit()

    def _fail(self, line):
        print(line, file=sys.stderr)
        self._set_status(line)
