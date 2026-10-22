"""What an agent is doing to the open document, for the top bar's agent chip and the 1-second outlines
(INTERACTION.md 1.18). The bridge owns one and feeds it every change it hears (its own document's and each joined
partner's); a change by an agent, or by a script an agent ran (it carries a session), counts.

- `chip`: {"state", "text", "count", "session", "who"}. "working" while changes keep arriving less than 5 s apart
  ("Claude is working · 6 changes"), "done" after 5 s of quiet ("Claude: 12 changes"), "" after Keep or Undo all.
- `flash`: ids of the items the agent changed in the last second (apps outline them, ChangeOutline.qml).
- `message`: "Claude: <what>", the agent's last change in words.
It only reads changes: it never moves the selection, the playhead or the scroll. Keep is not a change.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .history_rows import who_name

QUIET_MS = 5000      # no change for this long: the run has ended (or paused) and the chip offers Review
FLASH_MS = 1000      # how long a changed item's outline shows


class AgentWatch(QObject):
    changed = Signal()
    historyAsked = Signal(str)        # open the History sheet, on this run ("" = everything): the app's shell opens it

    def __init__(self, parent=None):
        super().__init__(parent)
        self._who, self._session, self._count, self._state = None, "", 0, ""
        self._flash, self._message, self._text = [], "", ""
        self._seen: dict[int, int] = {}          # per document: the newest step already counted
        self._quiet = self._timer(QUIET_MS, self._rest)
        self._fade = self._timer(FLASH_MS, self._unflash)

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
        self._flash = list(dict.fromkeys(k[0] for k in sorted(doc.history.keys(change), key=str)))
        self._quiet.start()
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
        """Show `text` on the chip as it stands (the layout check's long-text states: `agent-say <text>`)."""
        from rostrum_core import Who
        self._who = self._who or Who.agent("claude-code")
        self._state, self._text, self._message = state, text, text
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
        words = f"{n} change{'s' if n != 1 else ''}"
        text = self._text or (f"{name} is working · {words}" if self._state == "working" else f"{name}: {words}")
        return {"state": self._state, "text": text, "count": n, "session": self._session, "who": name}

    @Property("QVariantList", notify=changed)
    def flash(self):
        return list(self._flash)

    @Property(str, notify=changed)
    def message(self):
        return self._message
