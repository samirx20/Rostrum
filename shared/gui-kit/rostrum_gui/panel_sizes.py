"""The panel sizes a person set by hand (SPEC 2d-design-v2 §1.2): the settings panel's width and the timeline's
height, per app and per arrangement ("stacked": timeline below the frame, "side": beside it). Screen state kept in the
person's settings (userhome: a scripted run gets its scratch home), never in the document, never changed by an agent.
A size of -1 means "automatic" (the frame-driven layout picks it; double-clicking a panel edge gives it back).

QML (context property `panelSizes`): get(arrangement, panel) -> int, set(arrangement, panel, size).
"""
from __future__ import annotations

import json

from PySide6.QtCore import QObject, Slot

from rostrum_core import userhome


class PanelSizes(QObject):
    def __init__(self, app: str, parent=None):
        super().__init__(parent)
        self._path = userhome.home() / "panels.json"
        self._app = app
        self._sizes = self._read().get(app, {})

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))   # a broken file fails loudly

    @Slot(str, str, result=int)
    def get(self, arrangement: str, panel: str) -> int:
        return int(self._sizes.get(f"{arrangement}.{panel}", -1))

    @Slot(str, str, int)
    def set(self, arrangement: str, panel: str, size: int) -> None:
        key = f"{arrangement}.{panel}"
        if self._sizes.get(key, -1) == size:
            return
        with userhome.locked(self._path):
            every = self._read()
            mine = every.setdefault(self._app, {})
            if size < 0:
                mine.pop(key, None)
            else:
                mine[key] = int(size)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(every, indent=1), encoding="utf-8")
            self._sizes = mine
