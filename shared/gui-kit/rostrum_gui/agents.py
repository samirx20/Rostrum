"""What Help → Connect an AI agent shows and does: the coding agents found on this computer first, each with Add /
Remove for this app's MCP server, and the exact by-hand text for every agent. All the knowledge lives in
`rostrum_connect` (shared/mcp): this is only its screen side. Add and Remove run off the screen's thread (an agent's
own command line can take a few seconds) and report back in plain words through `message`."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

try:
    import rostrum_connect
except ImportError:                       # the install and a checkout both hold it at <root>/shared/mcp
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mcp"))
    import rostrum_connect
from rostrum_connect import byhand, connect

NAMES = {"2d": "Rostrum2D", "sound": "RostrumSound"}


class Agents(QObject):
    changed = Signal()
    _done = Signal(str, bool)             # from the worker thread: message, ok

    def __init__(self, app: str, parent=None):
        super().__init__(parent)
        self.app, self._rows, self._message, self._ok, self._busy = app, [], "", True, ""
        self._done.connect(self._finish)

    def _row(self, found) -> dict:
        a = found.agent
        try:
            s = connect.status(a.id, self.app)
            state = "ours" if s.ours else "foreign" if s.foreign else "none"
        except Exception as e:            # an unreadable config file: say so on its row, never hide the agent
            state, s = "error: " + str(e), None
        hand = byhand.by_hand(a.id, self.app)
        return {"id": a.id, "name": a.name, "installed": found.installed, "how": found.how, "state": state,
                "file": str(s.file) if s else hand["file"], "command": hand["command"] or "", "snippet": hand["snippet"],
                "deeplink": hand["deeplink"] or "", "steps": hand["steps"], "docs": a.docs}

    @Slot()
    def refresh(self):
        self._load()
        self.changed.emit()

    def _load(self):
        self._rows = [self._row(f) for f in connect.agents_found()]

    @Property("QVariantList", notify=changed)
    def rows(self) -> list:
        if not self._rows:
            self._load()          # no `changed` from inside a read: that is a binding loop in the screen
        return self._rows

    @Property(str, constant=True)
    def appName(self) -> str:
        return NAMES.get(self.app, "Rostrum")

    @Property(str, constant=True)
    def server(self) -> str:
        return f"rostrum-{self.app}"

    @Property(str, notify=changed)
    def message(self) -> str:
        return self._message

    @Property(bool, notify=changed)
    def messageOk(self) -> bool:
        return self._ok

    @Property(str, notify=changed)
    def busy(self) -> str:
        """The id of the agent being changed right now, else ''."""
        return self._busy

    def _run(self, agent_id: str, fn):
        if self._busy:
            return
        self._busy, self._message = agent_id, ""
        self.changed.emit()

        def work():
            try:
                r = fn(agent_id, self.app)
                text = r.summary + (f" A copy of the file as it was: {r.backup}" if getattr(r, "backup", None) else "")
                self._done.emit(text, bool(r.ok))
            except Exception as e:        # fail loudly: the person reads exactly what went wrong
                self._done.emit(f"Error: {e}", False)
        threading.Thread(target=work, daemon=True, name=f"connect-{agent_id}").start()

    @Slot(str, bool)
    def _finish(self, text: str, ok: bool):
        self._busy, self._message, self._ok = "", text, ok
        self.refresh()

    @Slot(str)
    def add(self, agent_id: str):
        self._run(agent_id, connect.add)

    @Slot(str)
    def remove(self, agent_id: str):
        self._run(agent_id, connect.remove)

    @Slot(str)
    def copy(self, text: str):
        QGuiApplication.clipboard().setText(text)

    @Slot(str)
    def openLink(self, url: str):
        QDesktopServices.openUrl(QUrl(url))
