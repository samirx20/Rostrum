"""One window per open document: New, Open, Save As and Restore make a fresh bridge and window for the document they
open, then close the old ones (the canvas engine, the image providers and the marker watch all belong to one
project). The Files object (files.py) lives across them, as QML's `files`.
A document opens with the playhead at 0, like the ruler says. (It used to open on the first frame where something comes
into view, which put the playhead at 0.44 s on a project whose title fades in, with nothing to say why.)
"""
from __future__ import annotations

from pathlib import Path

from rostrum_gui import start

from .bridge2d import Bridge2D
from .files import Files

QML = Path(__file__).resolve().parents[1] / "qml" / "Main.qml"


class Session:
    def __init__(self, size=(1600, 960)):
        self.size, self.bridge, self.engine, self.win = size, None, None, None
        self.files = Files(self)

    def show(self, doc, live: bool, comp_id=None, ask_recovery: bool = True):
        """Open `doc` in a new window (live: saved after every change, --doc); the old window closes without asking."""
        bridge = Bridge2D(doc, comp_id, autosave=live)
        bridge.files = self.files
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
