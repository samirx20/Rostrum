"""The document bridge: what QML sees of one rostrum_core Document, and the only way QML changes it.

Every edit is an operation through doc.apply (a scrub through doc.gesture: one change for the whole drag),
recorded with the person's name, so undo, history and "who changed what" work the same as for agents.
The bridge listens to the document (doc.subscribe), so an agent's or script's change shows up in place too.
Selection (one item, or several: `selectMany`, the panel then shows what they share, many.py), the More row, open
groups and the search are screen state, not document changes. A refused edit fails loudly: the error
line goes to the console and to `status` (the top bar shows it in red).

An app adapts it by overriding the hooks (the one place each decision lives): `label_of` (an item's name),
`kind_label` (its kind in words), `selection_label` (several items: "2 layers"), `extra_commands` (its own Ctrl K
commands),
`edit_call` (a screen edit -> its operation call), `shown_values` (the values the inspector shows),
`anim_state` / `animate_calls` (an app with keys: the key mark on a row and what its toggle does),
`on_page` (fields the page's own controls already show, which the inspector leaves out).
Selection and rows: bridge_select.py. One history with other documents: bridge_history.py. Edit slots: bridge_edits.py. The settings panel by importance (opt-in
`sections = True`): bridge_sections.py. Slots from other modules: parts.py (mix-ins, `attach`, `handle` / `invoke`).
The kit's state lives on `self._kit` and its names are guarded (kit_state.py): an app can't overwrite them by accident.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import RostrumError, Who, codes

from . import kit_state, rows
from .bridge_edits import EditSlots
from .bridge_history import HistoryParts
from .bridge_sections import SectionSlots
from .bridge_select import SelectSlots
from .edits import field_call
from .kit_state import KitState
from .model import RowsModel
from .parts import Parts


def name_of(item: dict) -> str:
    return str(item.get("name") or item["id"])


class DocBridge(SelectSlots, SectionSlots, EditSlots, HistoryParts, Parts, QObject):
    selectionChanged = Signal()
    docChanged = Signal()
    statusChanged = Signal()
    searchChanged = Signal()
    rowsChanged = Signal()                  # the rows' values or validity changed (nothingFound follows it)
    fieldRevealed = Signal(str)             # revealField: the Inspector scrolls to the row and focuses it

    def __init__(self, doc, who=None, parent=None):
        kit_state.check(type(self))         # an app class that redefines a kit name fails here, by name
        super().__init__(parent)
        self._kit = KitState(doc.history.mark())
        self.doc, self.who = doc, who or Who.person("sam")
        self.model = RowsModel(rows.ROLES, self)
        self._unsubscribe = doc.subscribe(self._on_doc)
        self.select(self._first())

    def __setattr__(self, name, value):
        """A kit name set on the bridge (an app's `self._refresh = ...`) would replace the kit's: refused, loudly."""
        names = kit_state.check(type(self))
        if name in names and (name not in kit_state.ONCE or name in self.__dict__):
            raise AttributeError(f"{type(self).__name__}.{name} is the kit's (rostrum_gui); use another name")
        super().__setattr__(name, value)

    @property
    def _sel(self) -> str:
        """The primary selected item's id ("" = none), for apps (read-only; `select` / `selectMany` change it)."""
        return self._kit.sel

    # ---- reads for QML ----------------------------------------------------------------------------------------
    @Property(str, notify=selectionChanged)
    def selected(self):
        return self._kit.sel

    @Property("QVariantList", notify=selectionChanged)
    def selection(self):
        return list(self._kit.selection)

    @Property("QVariantMap", notify=selectionChanged)
    def selectedItem(self):
        """{id, label, kind, kindLabel, count}: the primary item's; several selected: "3 items" and their kind (in
        words) when it is one, else "Different kinds"."""
        if not self._kit.sel:
            return {"id": "", "label": "", "kind": "", "kindLabel": "", "count": 0}
        its = [self.doc.item(i) for i in self._kit.selection]
        kinds = {it["type"] for it in its}
        one = len(kinds) == 1
        return {"id": its[0]["id"], "label": self.selection_label(self._kit.selection),
                "kind": its[0]["type"] if one else "", "count": len(its),
                "kindLabel": self.kind_label(its[0]) if one else "Different kinds"}

    @Property("QVariantList", notify=docChanged)
    def items(self):
        return [{"id": i["id"], "label": self.label_of(i), "kind": i["type"]} for i in self._items()]

    @Property(QObject, constant=True)
    def rows(self):
        return self.model

    @Property(bool, notify=selectionChanged)
    def moreOpen(self):
        return self._kit.more

    @Property(bool, constant=True)
    def sectioned(self):
        """The Inspector shows the "Find a setting" box and fold rows (rows by importance, `sections = True`)."""
        return self.sections

    @Property(str, notify=searchChanged)
    def search(self):
        return self._kit.search

    @Property(bool, notify=rowsChanged)
    def nothingFound(self):
        """A search is typed and no setting that applies matches it ("No setting matches")."""
        return bool(self._kit.search.strip()) and not any(r["valid"] for r in self.model.rows if r["row"] == "param")

    @Property(int, notify=docChanged)
    def historyCount(self):
        return self.changes_since_open()

    @Property(str, notify=statusChanged)
    def status(self):
        return self._kit.status

    # ---- screen state ---------------------------------------------------------------------------------------
    @Slot(str, "QVariantList", result="QVariant")
    def invoke(self, name, args):
        """Call a handler registered with `handle` (parts.py)."""
        return self._invoke(name, args)

    # ---- hooks (override in an app) -------------------------------------------------------------------------
    def label_of(self, item: dict) -> str:
        return name_of(item)

    def selection_label(self, ids: list[str]) -> str:
        """What the selection is called (panel title, Ctrl K hints): one item's name, else "N items" (2D: "2 layers")."""
        return self.label_of(self.doc.item(ids[0])) if len(ids) == 1 else f"{len(ids)} items"

    def extra_commands(self) -> list[dict]:
        """The app's own commands for Ctrl K, after the operations': {"key", "label", "hint", and "calls" (one
        change) or "do" (a function, for what isn't an operation, e.g. Copy)}; optional "words", "weight"."""
        return []

    def kind_label(self, item: dict) -> str:
        """An item's kind in words, for the panel's subtitle and Ctrl K's hints (default: its type, capitalised)."""
        return item["type"][:1].upper() + item["type"][1:]

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
    def _heard(self, change):
        """A change made by someone else (an agent, a script, another app) shows in the status as who did what."""
        if change is not None and change.who != self.who:
            self._set_status(f"{change.who}: {change.label}")
        self.docChanged.emit()

    def _on_doc(self, event):
        self._follow_doc()
        self._heard(event.change if event.kind == "change" else None)

    @Slot(str)
    def say(self, text):
        """Put an app's own one-line message (a save, a refused open) in the top bar's status, where every app's
        "what just happened" goes; a line starting "Error" shows red."""
        self._set_status(text)

    def _set_status(self, text):
        self._kit.status = text
        self.statusChanged.emit()

    def _fail(self, line):
        print(line, file=sys.stderr)
        self._set_status(line)
