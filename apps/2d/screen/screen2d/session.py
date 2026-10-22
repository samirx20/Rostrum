"""One window per open document: New, Open, Save As and Restore make a fresh bridge and window for the document they
open, then close the old ones (the canvas engine, the image providers and the marker watch all belong to one
project). The Files object (files.py) lives across them, as QML's `files`.
"""
from __future__ import annotations

import math
from pathlib import Path

from rostrum2d.engine import EngineError
from rostrum2d.seen import first_seen
from rostrum_gui import start

from .bridge2d import Bridge2D
from .files import Files

QML = Path(__file__).resolve().parents[1] / "qml" / "Main.qml"


def opening_time(bridge) -> float:
    """Open on a frame worth seeing: the first moment something can be seen (rostrum2d.seen, the same rule as the
    Problems "never seen" check), on the frame at or after it; 0 when nothing is ever seen or a text can't be measured
    (the Problems list says why)."""
    try:
        t = first_seen(bridge.placed())
    except EngineError:
        return 0.0
    fps = bridge.comp()["fps"]
    return math.ceil((t or 0.0) * fps - 1e-6) / fps


class Session:
    def __init__(self, size=(1600, 960)):
        self.size, self.bridge, self.engine, self.win = size, None, None, None
        self.files = Files(self)

    def show(self, doc, live: bool, comp_id=None, ask_recovery: bool = True):
        """Open `doc` in a new window (live: saved after every change, --doc); the old window closes without asking."""
        bridge = Bridge2D(doc, comp_id, autosave=live)
        bridge.files = self.files
        bridge.setTime(opening_time(bridge))
        self.files.hold(doc, live, ask_recovery)
        _, engine, win = start(QML, {"backend": bridge, "painter": bridge.painter, "files": self.files}, self.size,
                               providers={"frame": bridge.frames.provider, "onion": bridge.painter.provider})
        old = (self.bridge, self.engine, self.win)
        self.bridge, self.engine, self.win = bridge, engine, win
        if old[0] is not None:
            old[2].setProperty("leaving", True)          # no "save changes?" for a window being replaced
            old[2].close()
            old[0]._unsubscribe()
            old[0].close()
            old[1].deleteLater()

    def fail(self, line: str):
        """A file action failed: said in the window's status line (red) and on the console."""
        if self.bridge is not None:
            self.bridge._fail(line)
        else:
            raise RuntimeError(line)

    def close(self):
        if self.bridge is not None:
            self.bridge.close()
