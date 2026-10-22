"""The document bridge: what QML sees of one rostrum_core Document, and the only way QML changes it.

Every edit is an operation through doc.apply (a scrub through doc.gesture: one change for the whole drag),
recorded with the person's name, so undo, history and "who changed what" work the same as for agents.
The bridge listens to the document (doc.subscribe), so an agent's or script's change shows up in place too.
Selection and the More row are screen state, not document changes. A refused edit fails loudly: the error
line goes to the console and to `status` (the top bar shows it in red).

An app adapts it by overriding the hooks (the one place each decision lives): `label_of` (an item's name),
`edit_call` (a screen edit -> its operation call), `shown_values` (the values the inspector shows),
`anim_state` / `animate_calls` (an app with keys: the key mark on a row and what its toggle does),
`on_page` (fields the page's own controls already show, which the inspector leaves out).
Edit slots: bridge_edits.py. Slots from other modules: parts.py (mix-ins, `attach`, `handle` / `invoke`).
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import RostrumError, Who, codes

from . import commands, rows
from .bridge_edits import EditSlots
from .edits import Scrub, field_call
from .model import RowsModel
from .parts import Parts


def name_of(item: dict) -> str:
    return str(item.get("name") or item["id"])


class DocBridge(EditSlots, Parts, QObject):
    selectionChanged = Signal()
    docChanged = Signal()
    statusChanged = Signal()

    def __init__(self, doc, who=None, parent=None):
        super().__init__(parent)
        self.doc, self.who = doc, who or Who.person("sam")
        self._sel, self._more, self._status = "", False, ""
        self._scrub: Scrub | None = None
        self._partners: list = []           # other documents in this person's one history (join_history)
        self._static: list[dict] = []
        self._parts_init()
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
        return {"id": it["id"], "label": self.label_of(it), "kind": it["type"]}

    @Property("QVariantList", notify=docChanged)
    def items(self):
        return [{"id": i["id"], "label": self.label_of(i), "kind": i["type"]} for i in self._items()]

    @Property(QObject, constant=True)
    def rows(self):
        return self.model

    @Property(bool, notify=selectionChanged)
    def moreOpen(self):
        return self._more

    @Property(int, notify=docChanged)
    def historyCount(self):
        """Changes in this person's one history: the document's and every joined partner's (e.g. the markers)."""
        return len(self.doc.history.changes) + sum(p.change_count() for p in self._partners)

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
        kind = self.doc.item(item_id)["type"] if item_id else ""
        self._static = rows.layout(self.doc.kind.registry.field_op(kind) if item_id else None, kind)
        self.model.reset(self._rows())      # a new selection swaps the list at once (no reveal animation)
        self.selectionChanged.emit()

    @Slot()
    def toggleMore(self):
        self._more = not self._more
        self.model.update(self._rows())
        self.selectionChanged.emit()

    @Slot(str, "QVariantList", result="QVariant")
    def invoke(self, name, args):
        """Call a handler registered with `handle` (parts.py)."""
        return self._invoke(name, args)

    def join_history(self, partner):
        """Another document edited from this screen joins the one undo history and the change count (AGENTS.md
        rule 3; rostrum_core.desk). `partner`: `history_doc()` (its Document now, or None), `stepped(doc)` (save and
        re-read after an undo / redo there), `change_count()`, `last_change()` and a `changed` signal."""
        self._partners.append(partner)
        partner.changed.connect(lambda: self._heard(partner.last_change()))

    # ---- hooks (override in an app) -------------------------------------------------------------------------
    def label_of(self, item: dict) -> str:
        return name_of(item)

    def edit_call(self, item_id, param, value) -> dict:
        return field_call(self.doc, item_id, param, value)

    def shown_values(self, item: dict) -> dict:
        return item

    def on_page(self, item: dict) -> set[str]:
        """Names of this item's fields that the page's own controls already show (a control appears once per
        screen); the inspector leaves them out, and a group whose members all went goes too."""
        return set()

    def anim_state(self, item: dict, param: str) -> str:
        return ""

    def list_choices(self, item: dict, param: str) -> list[dict]:
        """What a list param may hold, or a pick param may name, [{value, label}] (a list of choices uses its own options)."""
        return []

    def animate_calls(self, item_id, param) -> tuple[list[dict], str]:
        raise RostrumError(codes.UNKNOWN_OPERATION, "inspector", f'"{param}"', "can't be animated in this app")

    def expr_state(self, item: dict, param: str):
        """{"text", "note"} of the expression or binding driving this param; "" = none (the row shows its widget)."""
        return ""

    def clear_expr_calls(self, item_id, param) -> tuple[list[dict], str]:
        raise RostrumError(codes.UNKNOWN_OPERATION, "inspector", f'"{param}"', "has no expression in this app")

    # ---- inside ---------------------------------------------------------------------------------------------
    def _items(self):
        return [i for i in self.doc.items() if i["id"] != self.doc.data["id"]]

    def _first(self):
        return next((i["id"] for i in self._items()), "")

    def _commands(self):
        return commands.build(self.doc, [self._sel] if self._sel else [], self.label_of)

    def _rows(self):
        if not self._sel:
            return []
        it = self.doc.item(self._sel)
        evaluated = rows.evaluate(self._static, self.shown_values(it), self.doc.kind.facts(it, self.doc), self._more,
                                  lambda name: self.anim_state(it, name), lambda name: self.expr_state(it, name),
                                  lambda name: self.list_choices(it, name))
        return rows.omit(evaluated, self.on_page(it))

    def _heard(self, change):
        """A change made by someone else (an agent, a script, another app) shows in the status as who did what."""
        if change is not None and change.who != self.who:
            self._set_status(f"{change.who}: {change.label}")
        self.docChanged.emit()

    def _on_doc(self, event):
        if self._sel and not self.doc.has(self._sel):      # the selected item went away (e.g. undo of an add)
            self.select(self._first())
        else:
            self.model.update(self._rows())
            self.selectionChanged.emit()                   # its name may have changed (an agent's rename)
        self._heard(event.change if event.kind == "change" else None)

    @Slot(str)
    def say(self, text):
        """Put an app's own one-line message (a save, a refused open) in the top bar's status, where every app's
        "what just happened" goes; a line starting "Error" shows red."""
        self._set_status(text)

    def _set_status(self, text):
        self._status = text
        self.statusChanged.emit()

    def _fail(self, line):
        print(line, file=sys.stderr)
        self._set_status(line)
