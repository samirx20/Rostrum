"""The one adapter between an app's action list (actions.py) and its screen. Any app's bridge hosts one (2D's kit
DocBridge and Sound's own bridge alike) and hands it five plain functions, so the hub knows nothing about either
document: what the selection is (`facts_fn`), how to say it ("3 layers": `what_fn`), how to apply calls as ONE undo
step (`apply_fn`), how to run an app's own non-operation action (`do_fn`: copy, rename) and where a plain message
goes (`message_fn`: the status line).

QML reads `bar` (the context bar), `panel` (the settings panel's actions at its top), `offered` (the ids allowed now), calls `menu()` on right-click, `commands(query)` for Ctrl+K's "Do" group,
`run(id)` for a click, `previewStart(id)` / `previewEnd()` for a hover preview (an app that has one), and `key(job)` from the key map's shortcuts (`keys`); a hold key's release comes as
`keyUp(job)` (keyhold.py), and runs the release of the action its press ran: nothing if the press ran nothing. Every door re-reads the list at the
moment it is used, so a stale bar can never run an action that is no longer valid: it says why instead. An action
that raises is reported by name (qt_faults: the person sees "Select inside didn't work: …", a scripted run fails).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from . import commands as command_box
from . import action_views as views
from . import qt_faults
from .actions import ActionList
from .keyhold import KeyHold
from .match import starts


class ActionHub(QObject):
    barChanged = Signal()
    panelChanged = Signal()
    offeredChanged = Signal()

    def __init__(self, action_list: ActionList, facts_fn, what_fn, apply_fn, do_fn, message_fn, parent=None,
                 preview_fn=None, unpreview_fn=None):
        super().__init__(parent)
        self.list = action_list
        self._jobs = None
        self._facts, self._what, self._apply, self._do, self._say = facts_fn, what_fn, apply_fn, do_fn, message_fn
        self._preview, self._unpreview = preview_fn, unpreview_fn      # an app's hover preview (previewStart / previewEnd)
        self._bar: dict = {"what": "", "items": [], "more": []}
        self._panel: dict = {"rows": [], "more": []}
        self._offered: list = []
        self._held: dict[str, dict] = {}       # hold job -> the entry its press ran, until the key comes up
        self._hold = KeyHold(self, action_list.keymap)     # watches releases only when the map has hold keys
        self._later = QTimer(self)                          # refresh_later: once, when this turn of the loop is over
        self._later.setSingleShot(True)
        self._later.setInterval(0)
        self._later.timeout.connect(self.refresh)

    def _now(self):
        facts = self._facts()
        return facts, self.list.available(facts)

    @Property("QVariantMap", notify=barChanged)
    def bar(self):
        return self._bar

    @Property("QVariantMap", notify=panelChanged)
    def panel(self):
        """The settings panel's actions for this selection (action_views.panel), at its top."""
        return self._panel

    @Property("QVariantList", notify=offeredChanged)
    def offered(self):
        """The ids of every action this selection allows now (as of the last refresh): "is X offered?" without building
        a menu (a binding that built the whole right-click menu on every pick to look for one id cost ms per click)."""
        return self._offered

    @Property("QVariantList", constant=True)
    def keys(self):
        """Every key of this app (shared first): {job, keys, label, area, where}, for Shortcuts and Ctrl+/."""
        return self.list.keymap.entries()

    @Property("QVariantList", constant=True)
    def jobs(self):
        """The key map jobs some action runs: the shortcuts the hub answers (KeyMap.qml's `skip` is the rest)."""
        if self._jobs is None:          # worked out once: QML reads it for every key (3,400 reads at start, S59)
            self._jobs = sorted({j for j in (self.list.job_of(a) for a in self.list.actions) if j})
        return self._jobs

    def row_buttons(self) -> dict:
        """The buttons that sit on settings rows now ({param id: {label, id, menu}}, action_views.row_buttons)."""
        return views.row_buttons(self._now()[1])

    @Slot()
    def refresh(self):
        """Call after the selection or the document changed. Re-sends only what changed: a drag step that leaves the
        actions alone redraws neither row."""
        self._refreshed = True
        self._later.stop()
        facts, entries = self._now()
        bar, panel = views.bar(entries, self._what(facts)), views.panel(entries, self.list.short_menu)
        if bar != self._bar:
            self._bar = bar
            self.barChanged.emit()
        if panel != self._panel:
            self._panel = panel
            self.panelChanged.emit()
        offered = [e["id"] for e in entries]
        if offered != self._offered:
            self._offered = offered
            self.offeredChanged.emit()

    @Slot()
    def refresh_later(self):
        """`refresh` once the event being handled is done (connect a document change here): an action that changes
        the document and then picks what it made (Ctrl+G's group) refreshed for the change and again for the pick,
        each rebuilding the bar and the panel's buttons (~6-12 ms); a `refresh` meanwhile is that one."""
        self._later.start()

    @Slot(result="QVariantList")
    def menu(self):
        return views.menu(self._now()[1], self.list.short_menu)

    @Slot(str, result="QVariantList")
    def commands(self, query):
        facts, entries = self._now()
        found = views.commands(entries, self._what(facts))
        found = command_box.search(found, query) if query.strip() else found
        return found                                # only what can run now: an action that cannot is not listed (its reason is said when its key is pressed)

    @Slot(str, result=str)
    def whyNot(self, typed):
        """Ctrl+K: the line for an exact action name typed that isn't offered now ("" when it is, or no such name
        among the actions)."""
        facts = self._facts()
        t = typed.strip().lower()
        if not any(t in (a.id.lower(), a.label_for(facts).lower()) for a in self.list.actions):
            return ""
        return self.list.why_not(facts, typed)

    @Slot(str)
    def run(self, id_):
        facts, entries = self._now()
        entry = next((e for e in entries if e["id"] == id_), None)
        if entry is None:
            self._say(self.list.why_not(facts, id_) or f'"{id_}" can\'t run now.')
            return
        self._go(entry)

    @Slot(str)
    def previewStart(self, id_):
        """The pointer rests on an action: the app shows its would-be result, recording nothing (`preview_fn(calls)`).
        An action not valid now, one that is not a plain change (copy, rename) or an app with no preview: nothing."""
        entry = next((e for e in self._now()[1] if e["id"] == id_), None) if self._preview else None
        if entry and not entry["do"] and entry["calls"]:
            self._preview(entry["calls"])

    @Slot()
    def previewEnd(self):
        """The pointer left (or the row went): the app takes its preview back."""
        if self._unpreview:
            self._unpreview()

    @Slot(str)
    def key(self, job):
        """A shortcut pressed: run its action if valid now, else say why. A key with no action here does nothing."""
        entry, why = self.list.on_key(self._facts(), job)
        if entry:
            if entry["release"]:
                self._held[job] = entry
            self._go(entry)
        elif why:
            self._say(why)

    @Slot(str)
    def keyUp(self, job):
        """A hold key let go: the release of what its press ran (the press ran nothing, or a refusal: nothing)."""
        entry = self._held.pop(job, None)
        if entry:
            self._do(entry["release"], entry)
            self.refresh()

    def _go(self, entry):
        self._refreshed = False
        try:
            if entry["do"]:
                self._do(entry["do"], entry)
            else:
                self._apply(entry["calls"], entry["label"])
        except Exception:
            qt_faults.python_error(f'action "{entry["id"]}"', entry["label"])
        if not self._refreshed:         # the change's own listeners refreshed already (once per change is enough)
            self.refresh()
