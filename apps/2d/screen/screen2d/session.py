"""One window per open document: the kit's file model (rostrum_gui/project_files.py, QML `files`) calls `show` for
each document it opens (New, Open, Open recent, the sample, the start screen); this makes a fresh bridge and window
for it, then closes the old ones (the canvas engine, the image providers and the marker watch all belong to one
project). A document with a folder is live (Bridge2D: every change on disk at once, shared with agents' servers).
A document opens with the playhead at 0, like the ruler says.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QTimer
from rostrum_gui import guides, start
from rostrum_gui.app import free, stop
from rostrum_gui.project_files import ProjectFiles
from rostrum2d import fields as F, textsize

from . import bounds, project_picks
from .bridge2d import Bridge2D
from .files2d import FILES2D
from .spacekey import SpaceKey

QML = Path(__file__).resolve().parents[1] / "qml" / "Main.qml"
GUIDES = guides.entries(Path(__file__).resolve().parents[2] / "guides", [     # Help's guides (apps/2d/guides): for people;
    ("first-animation.md", "Making your first animation"), ("the-screen.md", "The screen"),   # the agent pages are
    ("drawing.md", "Drawing"), ("importing.md", "Importing pictures and files"),                # listed in README.md
    ("exporting.md", "Exporting a video"), ("files.md", "Files and settings"), ("timing-to-music.md", "Timing to music"),
    ("text-on-a-path.md", "Text on a path"), ("curve-editor.md", "The curve editor"),
    ("characters-sound-styles.md", "Characters, sound and styles"), ("README.md", "All guides")])


AHEAD_MS = 300                       # ms after the window shows: the panels of the piece's kinds start to be made
SWITCH_S = 0.001                     # s: Python's hand-over between threads (default 5 ms, a third of a frame)


def _measure_ahead(bridge):
    """The scene's texts measured now, on a thread of its own (textsize keeps each size): the engine reading a text's
    font for its first measure made the first pick of a text wait ~120 ms for its box. A failure is said by the screen's
    own first measure."""
    comp, t = bridge.placed(), bridge._t

    def measure():
        try:
            bounds.boxes(comp, t)
        except Exception:  # noqa: BLE001  the screen's own measure says it
            pass
    threading.Thread(target=measure, daemon=True, name="text-measure-ahead").start()


def _panels_ahead(bridge):
    """A moment after the window is up: the settings panel of each kind in the piece (the scene, the frame, a shape, a
    text, a group ...) made ahead, a few rows a frame (the kit's make_panels_ahead); after that the kit makes one for
    each kind that appears later (ready_new_kinds, told after every change). A kind's first pick, or the first Ctrl+G's
    group, made its whole panel in the frame after the click: ~25-130 ms."""
    comp = bridge.comp_id
    bridge._kit.ahead_filter = lambda it: it["type"] in F.LAYERS or it["id"] == comp
    QTimer.singleShot(AHEAD_MS, bridge, bridge.ready_new_kinds)
    QTimer.singleShot(2000, bridge, project_picks.warm_faces)       # the Font list's first faces


class Session:
    def __init__(self, size=(1600, 960), comp_id=None):
        sys.setswitchinterval(SWITCH_S)    # pictures are made on worker threads: the screen's thread waits for one at most this long
        self.size, self.bridge, self.engine, self.win, self.comp_id = size, None, None, None, comp_id
        self.files = ProjectFiles(FILES2D, self)
        self.space = None                                # Space: tap plays, hold + drag pans (spacekey.py; one per app)
        textsize.warm()                                  # the text-measuring engine starts while the window loads
        project_picks.warm()                             # ... and the font list is made (a text's Font pick)

    def show(self, doc):
        """Open `doc` in a new window; the old window closes (nothing to ask: every change is already on disk)."""
        bridge = Bridge2D(doc, self.comp_id)
        _measure_ahead(bridge)
        self.comp_id = None                              # --comp: the first window only
        bridge.files = self.files
        self.space = self.space or SpaceKey()
        _, engine, win = start(QML, {"backend": bridge, "painter": bridge.painter, "files": self.files,
                                     "guides": GUIDES, "spaceKey": self.space}, self.size,
                               providers={"frame": bridge.frames.provider,
                                          "onion": bridge.painter.provider, "wet": bridge.painter.wet.provider, "brushes": bridge.painter.previews,
                                          "paintthumbs": bridge._paint_layers.thumbs})
        bridge.painter.tilt.watch(win)                   # the pen's lean: Qt Quick's handlers don't give it
        bridge.colourPick.watch(win)                     # Alt picks a colour (paint_pick.py)
        self.space.watch(win)                            # Space: tap plays, hold pans (spacekey.py)
        old = (self.bridge, self.engine, self.win)
        self.bridge, self.engine, self.win = bridge, engine, win
        _panels_ahead(bridge)
        if old[0] is not None:                           # the window and its bindings first, then what they read
            stop(old[1], old[2], then=lambda: self._close(old[0]))

    @staticmethod
    def _close(bridge):
        """A project's bridge closed (engine, watchers, clocks), then freed with its parts (the kit's free): a lambda
        connected to one of its signals would otherwise keep it, its document and its pictures alive for good."""
        bridge._unsubscribe()
        bridge.close()
        free(bridge.painter, bridge)

    def close(self):
        """At quit: the start screen's picture is kept, then the window and its bindings go (the kit's stop), then the
        bridge they read."""
        self.files.close()
        stop(self.engine, self.win)
        self.engine = self.win = None
        if self.bridge is not None:
            self._close(self.bridge)
