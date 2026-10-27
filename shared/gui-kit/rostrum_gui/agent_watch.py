"""What an agent is doing to the open document, for the top bar's agent chip and the 1-second outlines
(INTERACTION.md 1.18). The bridge owns one and feeds it every change it hears (its own document's and each joined
partner's); a change by an agent, or by a script an agent ran (it carries a session), counts.

- `chip`: {"state", "text", "say", "count", "session", "who"}. "working" while changes keep arriving less than 5 s
  apart, "done" after 5 s of quiet, "" after Keep or Undo all. `text` is the chip ("Claude · 12 changes"); `say` the
  agent's sentence (its last change, or what it said), shown in the chip's dropdown.
- `flash`: ids of the items the agent changed in the last second, or that the person's own undo / redo just took back or
  put again (`flashMine`): apps outline them (ChangeOutline.qml), so an undo is seen (INTERACTION.md 1.21 rule 9).
- `message`: "Claude: <what>", the agent's last change in words.
It only reads changes: it never moves the selection, the playhead or the scroll. Keep is not a change.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .history_rows import who_name

QUIET_MS = 5000      # no change for this long: the run has ended (or paused) and the chip offers Review
FLASH_MS = 1000      # how long a changed item's outline fades (ChangeOutline.qml)
HOLD_MS = 250        # it shows whole this long first: the new picture lands after the change is heard (2D's engine frame)
KEEP_MS = HOLD_MS + FLASH_MS + 250      # the ids stay this long, so the outline is never taken away mid-fade
MOST = 400           # a step touching more items than this (a whole-song duplicate or its undo) outlines none: the top
                     # bar names it, thousands of outlines say nothing, and every view would search the list per item


class AgentWatch(QObject):
    changed = Signal()
    historyAsked = Signal(str)        # open the History sheet, on this run ("" = everything): the app's shell opens it

    def __init__(self, parent=None):
        super().__init__(parent)
        self._who, self._session, self._count, self._state = None, "", 0, ""
        self._flash, self._message, self._text, self._mine = [], "", "", False
        self._seen: dict[int, int] = {}          # per document: the newest step already counted
        self._quiet = self._timer(QUIET_MS, self._rest)
        self._fade = self._timer(KEEP_MS, self._unflash)

    def _timer(self, ms, fn):
        t = QTimer(self)
        t.setSingleShot(True)
        t.setInterval(ms)
        t.timeout.connect(fn)
        return t

    # ---- fed by the bridge --------------------------------------------------------------------------------------
    def heard(self, doc, change):
        """A change arrived in `doc` (any author). Only an agent's (or its script's) counts; each step once."""
        if change is None or self._seen.get(id(doc), 0) >= change.seq:
            return
        self._seen[id(doc)] = change.seq
        who = change.who
        if not (who.kind == "agent" or (who.kind == "script" and change.session)):
            if not change.original:      # the person's own undo / redo: what it took back flashes once (1.21 rule 9)
                self._flashed(doc, change, mine=True)
            return
        if not change.original:          # the agent's own undo / redo: shown, not counted as new work
            self._message = f"{who_name(who)}: {change.label}"
            self.changed.emit()
            return
        self._text = ""
        if self._state == "" or who != self._who or (change.session or "") != self._session:
            self._who, self._session, self._count = who, change.session or "", 0
        self._count += 1
        self._state = "working"
        self._message = f"{who_name(who)}: {change.label}"
        self._quiet.start()
        self._flashed(doc, change)

    def _flashed(self, doc, change, mine=False):
        """The items `change` touched get the 1-second outline (`mine`: the person's own undo, in the accent colour)."""
        ids = list(dict.fromkeys(k[0] for k in sorted(doc.history.keys(change), key=str)))
        self._flash = ids if len(ids) <= MOST else []
        self._mine = mine
        self._fade.start()
        self.changed.emit()

    def _rest(self):
        if self._state == "working":
            self._state = "done"
            self.changed.emit()

    def _unflash(self):
        self._flash = []
        self.changed.emit()

    def say(self, text, state="done"):
        """Put `text` in the chip's dropdown as the agent's sentence (the layout check's long-text states: `agent-say`)."""
        from rostrum_core import Who
        self._who = self._who or Who.agent("claude-code")
        self._state, self._text, self._message = state, text, text
        self.changed.emit()

    @Slot("QVariantList")
    def flashItems(self, ids):
        """Flash these items once, as the person's own (accent): an app's own edit that a person should see land (a
        copy made off screen, a track added from the Library). Every view that outlines `flash` shows it."""
        self._flash, self._mine = [str(i) for i in ids] if len(ids) <= MOST else [], True
        self._fade.start()
        self.changed.emit()

    # ---- QML ------------------------------------------------------------------------------------------------------
    @Slot(str)
    def askHistory(self, session):
        """Review (or Ctrl+H, or the change count): ask the shell to open History, on `session` when given."""
        self.historyAsked.emit(session)

    @Slot()
    def keep(self):
        """Keep: the person has seen the run. The chip goes; nothing in the document changes."""
        self._quiet.stop()
        self._state, self._count = "", 0
        self.changed.emit()

    def forget(self, session):
        """After Undo all of `session`: the chip goes (the run is in History, taken back)."""
        if session == self._session:
            self.keep()

    @Property("QVariantMap", notify=changed)
    def chip(self):
        if not self._state:
            return {"state": "", "text": "", "count": 0, "session": "", "who": ""}
        name, n = who_name(self._who), self._count
        text = f"{name} · {n} change{'s' if n != 1 else ''}"
        say = self._text or self._message or (f"{name} is working." if self._state == "working" else "")
        return {"state": self._state, "text": text, "say": say, "count": n, "session": self._session, "who": name}

    @Property("QVariantList", notify=changed)
    def flash(self):
        return list(self._flash)

    @Property(bool, notify=changed)
    def flashMine(self):
        """The flash is the person's own undo / redo (ChangeOutline draws it in the accent colour, not the agent's)."""
        return self._mine

    @Property(str, notify=changed)
    def message(self):
        return self._message
