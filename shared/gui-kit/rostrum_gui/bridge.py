"""The document bridge: what QML sees of one rostrum_core Document, and the only way QML changes it.

Every edit is an operation through doc.apply (a scrub through doc.gesture: one change for the whole drag; its steps
send `docStepped`, its end `docChanged`),
recorded with the person's name, so undo, history and "who changed what" work the same as for agents.
The bridge listens to the document (doc.subscribe), so an agent's or script's change shows up in place too.
Selection (one item, or several: `selectMany`, the panel then shows what they share, many.py), the More row, open
groups and the search are screen state, not document changes. A refused edit fails loudly: the error
line goes to the console and to `status` (the top bar shows it in red).

An app adapts it by overriding the hooks (the one place each decision lives): `label_of` (an item's name),
`kind_label` (its kind in words), `subtitle` (the line under the panel's name), `selection_label` (several items: "2 layers"), `extra_commands` (its own Ctrl K
commands),
`edit_call` (a screen edit -> its operation call), `shown_values` (the values the inspector shows),
`anim_state` / `animate_calls` (an app with keys: the key mark on a row and what its toggle does),
`on_page` (fields the page's own controls already show, which the inspector leaves out).
Selection and rows: bridge_select.py. One history with other documents: bridge_history.py. History rows, Undo all,
versions, ↶ ↷ labels: bridge_review.py (the agent chip: agent_watch.py). Edit slots: bridge_edits.py. The settings panel by importance (opt-in
`sections = True`): bridge_sections.py. Slots from other modules: parts.py (mix-ins, `attach`, `handle` / `invoke`).
The kit's state lives on `self._kit` and its names are guarded (kit_state.py): an app can't overwrite them by accident.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import RostrumError, Who, codes

from . import kit_state, news, qt_faults, rows
from . import touched as touch
from .agent_watch import AgentWatch
from .bridge_edits import EditSlots
from .bridge_history import HistoryParts
from .bridge_review import ReviewSlots
from .bridge_sections import SectionSlots
from .bridge_select import SelectSlots
from .edits import field_call
from .history_rows import who_name
from .kit_state import KitState
from .row_pages import RowPages
from .parts import Parts


def name_of(item: dict) -> str:
    return str(item.get("name") or item["id"])


class DocBridge(SelectSlots, SectionSlots, EditSlots, ReviewSlots, HistoryParts, Parts, QObject):
    selectionChanged = Signal()             # what the selection shows changed: its items, name, kind or the More row
    selectedItemsChanged = Signal()         # which items are selected changed (never a mere document edit)
    docChanged = Signal()                   # the document changed for good: an edit, undo, a drag's drop or Escape
    docStepped = Signal()                   # a step of an open drag (a preview): only what the person watches move follows
    findAsked = Signal()                    # Ctrl+K's "Find a setting" (job find_setting): the settings panel opens its find box
    statusChanged = Signal()
    searchChanged = Signal()
    rowsChanged = Signal()                  # the rows' values or validity changed (nothingFound follows it)
    panelShown = Signal()                   # a new selection's panel is shown (a pointer's pick: the frame after its
                                            # highlight); what only the panel and the context bar show follows this
    fieldRevealed = Signal(str)             # revealField: the Inspector scrolls to the row and focuses it
    countChanged = Signal()                 # historyCount moved (sent with docChanged, only then: _history_check)
    historyChanged = Signal()               # ↶ ↷ labels or versions changed (the same)
    faultSeen = Signal(str)                 # qt_faults heard an error in the app: its plain line, for the top bar

    def __init__(self, doc, who=None, parent=None):
        kit_state.check(type(self))         # an app class that redefines a kit name fails here, by name
        super().__init__(parent)
        self._kit = KitState(doc.history.mark())
        self.doc, self.who = doc, who or Who.person("sam")
        self.model = RowPages(rows.ROLES, self)            # the panel's rows: a list per kind's layout (row_pages.py)
        self._kit.agent = AgentWatch(self)
        self._kit.paced = news.OnceAFrame(self._step_rows, self)   # a drag's steps: the rows once per screen refresh
        self._history_check()                              # the count and ↶ ↷ as the window opens
        self.docChanged.connect(self._history_check)      # first: the top bar's count and ↶ ↷ read it
        self._unsubscribe = doc.subscribe(self._on_doc)
        self.faultSeen.connect(self._fault_said)           # queued from a worker thread: shown on the screen's thread
        qt_faults.tell(self._fault_heard)                  # an error in the app is said in the top bar, never only logged
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
    @Property(str, notify=selectedItemsChanged)
    def selected(self):
        return self._kit.sel

    @Property("QVariantList", notify=selectedItemsChanged)
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
                "kindLabel": self.kind_label(its[0]) if one else "Different kinds",
                "subtitle": self.subtitle(its[0]) if one else "Different kinds"}

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
        fx = self._kit.handlers.get("effects")         # an effect the search names counts as a match (effects.py)
        effect = fx is not None and fx().shown
        return bool(self._kit.search.strip()) and not effect and not any(r["valid"] for r in self.model.rows if r["row"] == "param")

    @Property(bool, constant=True)
    def typesExpressions(self):
        """A number field may take a typed "=…" (sent whole to edit_call): the app has expressions, which is when it
        overrides clear_expr_calls (2D). Elsewhere "=5" is just 5."""
        return type(self).clear_expr_calls is not DocBridge.clear_expr_calls

    # The count, ↶ ↷ and versions: worked out once per change (_history_check), read from there by every binding
    @Property(int, notify=countChanged)
    def historyCount(self):
        return self._kit.told[0]

    # History, ↶ ↷ and the agent chip (reads in bridge_review.py; Qt properties must sit on the QObject class)
    undoLabel = Property(str, lambda self: self._kit.told[1][0], notify=historyChanged)    # "" = nothing to undo
    redoLabel = Property(str, lambda self: self._kit.told[1][1], notify=historyChanged)
    versions = Property("QVariantList", lambda self: list(self._kit.told[1][2]), notify=historyChanged)
    agent = Property(QObject, lambda self: self._kit.agent, constant=True)    # agent_watch.AgentWatch

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

    def subtitle(self, item: dict) -> str:
        """The grey line under the panel's name (default: the kind in words; an app whose name and fields already say
        it returns "" or a word of its own)."""
        return self.kind_label(item)

    def edit_call(self, item_id, param, value) -> dict:
        return field_call(self.doc, item_id, param, value)

    def shown_values(self, item: dict) -> dict:
        return item

    def facts_of(self, item: dict) -> dict:
        """The facts the item's rows are evaluated with (valid_when): the kind's, and an app adds what only its screen
        knows (3D: `animating`, on the Animate page)."""
        return self.doc.kind.facts(item, self.doc)

    def on_page(self, item: dict) -> set[str]:
        """Names of this item's fields that the page's own controls already show (a control appears once per
        screen); the inspector leaves them out, and a group whose members all went goes too."""
        return set()

    def starts(self, item: dict) -> dict:
        """{field: value} a new item of this kind may start with besides the field's default (a tool's own start): a
        settings group opens only for a value the person changed from both."""
        return {}

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
    def _heard(self, change, doc=None):
        """A change made by someone else (an agent, a script, another app) shows in the status as who did what
        ("Claude: Moved title"); the agent watch counts an agent's (doc: where it was made; None = this document)."""
        if doc is not None and doc is not self.doc:
            self._kit.touched = None                       # another document's change: this one's parts can't tell
        if change is not None and change.who != self.who:
            self._set_status(f"{who_name(change.who, self.who)}: {change.label}")
        self._kit.agent.heard(doc or self.doc, change)
        self.docChanged.emit()

    def _on_doc(self, event):
        """A drag's step (a gesture preview) is only docStepped: the rows' values and the picture follow it live; the
        actions row, history, ↶ ↷ and item lists wait for docChanged, sent once when the drag ends (its change or reset).
        First, what the change or step touched (touched.py): every part reads it to skip work elsewhere."""
        self._kit.touched = touch.of(self.doc, event)
        self._follow_doc(event.kind == "preview")
        if event.kind == "preview":
            self.docStepped.emit()
            return
        self._heard(event.change if event.kind == "change" else None)

    def touched(self):
        """What the change being announced touched (touched.Touched: `reaches(doc, ids)`); None = can't tell, so a
        part redoes its work. Read it in a docChanged / outline listener to skip a change that is elsewhere."""
        return self._kit.touched

    def reached(self, ids) -> bool:
        """The change being announced touched `ids` (or items above or inside them), or can't tell."""
        t = self._kit.touched
        return t is None or t.reaches(self.doc, list(ids))

    def _history_check(self):
        """The count, the ↶ ↷ labels and the versions, worked out once per change (each scans the history) and kept:
        every read (the top bar, the Inspector, an app's binding, Python) takes the kept value. Their own signals are
        sent only when they changed: on docChanged every binding that reads them ran again on every edit (the top bar
        re-measured its words each time), and each read worked them out again (7 history scans per Undo)."""
        k, count = self._kit, self.changes_since_open()
        labels = (self.next_undo_label(), self.next_redo_label(), self.versions_list())
        if count != k.told[0]:
            k.told[0] = count
            self.countChanged.emit()
        if labels != k.told[1]:
            k.told[1] = labels
            self.historyChanged.emit()

    @Slot(str)
    def setFocusArea(self, name):
        """The area that takes the keys (AppShell.focusArea, named by the app's `areaNames`), for inspect_screen."""
        self._focus_area = name

    @Slot(str)
    def say(self, text):
        """Put an app's own one-line message (a save, a refused open) in the top bar's status, where every app's
        "what just happened" goes; a line starting "Error" shows red."""
        self._set_status(text)

    @Slot(str)
    def refuse(self, why):
        """A typed entry that was refused (FieldFrame's `problem`: "“zzz” is not a colour …"): said in the top bar in
        red as well as in the box, since a hover tip never shows to someone who has just clicked the box."""
        self._set_status(why, True)

    def _set_status(self, text, failed=None):
        self._kit.status = text
        self._failed = text.startswith("Error") if failed is None else failed
        self.statusChanged.emit()

    @Property(bool, notify=statusChanged)
    def statusFailed(self):
        """The status is a refusal (the top bar shows it in red)."""
        return getattr(self, "_failed", False)

    def _fail_error(self, e, fallback):
        """An operation's error (or any exception) as a refusal: the full line to the console, the person's words to the top bar."""
        self._fail(e.line() if hasattr(e, "line") else fallback, e.person() if hasattr(e, "person") else None)

    def _fault_heard(self, line):           # any thread (qt_faults): the signal carries it to the screen's thread
        self.faultSeen.emit(line)

    @Slot(str)
    def _fault_said(self, line):
        self._set_status(line, True)

    def _fail(self, line, shown=None):
        """`line`: the full developer line (console, agents); `shown`: the person's sentence for the top bar
        (RostrumError.person()); the line itself when none."""
        print(line, file=sys.stderr)
        self._set_status(shown or line, True)
