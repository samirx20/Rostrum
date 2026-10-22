"""The one adapter between an app's action list (actions.py) and its screen. Any app's bridge hosts one (2D's kit
DocBridge and Sound's own bridge alike) and hands it five plain functions, so the hub knows nothing about either
document: what the selection is (`facts_fn`), how to say it ("3 layers": `what_fn`), how to apply calls as ONE undo
step (`apply_fn`), how to run an app's own non-operation action (`do_fn`: copy, rename) and where a plain message
goes (`message_fn`: the status line).

QML reads `bar` (the context bar), calls `menu()` on right-click, `commands(query)` for Ctrl+K's "Do" group,
`run(id)` for a click, and `key(job)` from the key map's shortcuts (`keys`). Every door re-reads the list at the
moment it is used, so a stale bar can never run an action that is no longer valid: it says why instead.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from . import commands as command_box
from . import action_views as views
from .actions import ActionList


class ActionHub(QObject):
    barChanged = Signal()

    def __init__(self, action_list: ActionList, facts_fn, what_fn, apply_fn, do_fn, message_fn, parent=None):
        super().__init__(parent)
        self.list = action_list
        self._facts, self._what, self._apply, self._do, self._say = facts_fn, what_fn, apply_fn, do_fn, message_fn
        self._bar: dict = {"what": "", "items": [], "more": []}

    def _now(self):
        facts = self._facts()
        return facts, self.list.available(facts)

    @Property("QVariantMap", notify=barChanged)
    def bar(self):
        return self._bar

    @Property("QVariantList", constant=True)
    def keys(self):
        """Every key of this app (shared first): {job, keys, label, area, where}, for Shortcuts and Ctrl+/."""
        return self.list.keymap.entries()

    @Property("QVariantList", constant=True)
    def jobs(self):
        """The key map jobs some action runs: the shortcuts the hub answers (KeyMap.qml's `skip` is the rest)."""
        return sorted({j for j in (self.list.job_of(a) for a in self.list.actions) if j})

    @Slot()
    def refresh(self):
        """Call after the selection or the document changed."""
        facts, entries = self._now()
        self._bar = views.bar(entries, self._what(facts))
        self.barChanged.emit()

    @Slot(result="QVariantList")
    def menu(self):
        return views.menu(self._now()[1])

    @Slot(str, result="QVariantList")
    def commands(self, query):
        facts, entries = self._now()
        found = views.commands(entries, self._what(facts))
        return command_box.search(found, query) if query.strip() else found

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
    def key(self, job):
        """A shortcut pressed: run its action if valid now, else say why. A key with no action here does nothing."""
        entry, why = self.list.on_key(self._facts(), job)
        if entry:
            self._go(entry)
        elif why:
            self._say(why)

    def _go(self, entry):
        if entry["do"]:
            self._do(entry["do"], entry)
        else:
            self._apply(entry["calls"], entry["label"])
        self.refresh()
