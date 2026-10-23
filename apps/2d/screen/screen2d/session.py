"""One window per open document: the kit's file model (rostrum_gui/project_files.py, QML `files`) calls `show` for
each document it opens (New, Open, Open recent, the sample, the start screen); this makes a fresh bridge and window
for it, then closes the old ones (the canvas engine, the image providers and the marker watch all belong to one
project). A document with a folder is live (Bridge2D: every change on disk at once, shared with agents' servers).
A document opens with the playhead at 0, like the ruler says.
"""
from __future__ import annotations

from pathlib import Path

from rostrum_gui import guides, start
from rostrum_gui.app import stop
from rostrum_gui.project_files import ProjectFiles

from . import brush_presets
from .bridge2d import Bridge2D
from .files2d import FILES2D
from .spacekey import SpaceKey

QML = Path(__file__).resolve().parents[1] / "qml" / "Main.qml"
GUIDES = guides.entries(Path(__file__).resolve().parents[2] / "guides", [     # Help's guides (apps/2d/guides): for people;
    ("first-animation.md", "Making your first animation"), ("the-screen.md", "The screen"),   # the agent pages are
    ("drawing.md", "Drawing"), ("importing.md", "Importing pictures and files"),                # listed in README.md
    ("exporting.md", "Exporting a video"), ("files.md", "Files and settings"), ("timing-to-music.md", "Timing to music"),
    ("text-on-a-path.md", "Text on a path"), ("curve-editor.md", "The curve editor"),
    ("characters-sound-camera.md", "Characters, sound, camera and styles"), ("README.md", "All guides")])


class Session:
    def __init__(self, size=(1600, 960), comp_id=None):
        self.size, self.bridge, self.engine, self.win, self.comp_id = size, None, None, None, comp_id
        self.files = ProjectFiles(FILES2D, self)
        self.space = None                                # Space: tap plays, hold + drag pans (spacekey.py; one per app)

    def show(self, doc):
        """Open `doc` in a new window; the old window closes (nothing to ask: every change is already on disk)."""
        bridge = Bridge2D(doc, self.comp_id)
        self.comp_id = None                              # --comp: the first window only
        bridge.files = self.files
        self.space = self.space or SpaceKey()
        _, engine, win = start(QML, {"backend": bridge, "painter": bridge.painter, "files": self.files,
                                     "guides": GUIDES, "spaceKey": self.space}, self.size,
                               providers={"frame": bridge.frames.provider, "framecrop": bridge.frames.crops,
                                          "onion": bridge.painter.provider, "brushes": brush_presets.PreviewProvider()})
        old = (self.bridge, self.engine, self.win)
        self.bridge, self.engine, self.win = bridge, engine, win
        if old[0] is not None:                           # the window and its bindings first, then what they read
            stop(old[1], old[2], then=lambda: (old[0]._unsubscribe(), old[0].close()))

    def close(self):
        """At quit: the start screen's picture is kept, then the window and its bindings go (the kit's stop), then the
        bridge they read."""
        self.files.close()
        stop(self.engine, self.win)
        self.engine = self.win = None
        if self.bridge is not None:
            self.bridge.close()
