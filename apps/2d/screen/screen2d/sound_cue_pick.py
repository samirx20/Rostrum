"""Add a sound here… (UX_SPEC 3.28 Sync sound): one layer selected, in a project with sound → the action opens a small
popover listing sounds (Sound's library and the person's sound folders, read-only), with a search box; a click ties
that sound to the layer's start (rostrum2d/sound_cues.cue: the clip goes into Sound's song, timed by a marker that
follows the layer). The agents' edit_sound_cue runs the same function. Offered to QML as `backend.cuePick`.
The search reads the libraries off the screen's thread (a second or two), newest words win (the kit's PictureWorker:
one thread, only the latest job waits).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import sound_cues
from rostrum_gui.frames import PictureWorker


class _Search(PictureWorker):
    """The library search on its own thread: (serial, words) in, (serial, rows) out; a failure is the worker's `failed`."""
    found = Signal(int, list)

    def open_engine(self):
        return None                 # reads files only, no engine

    def handle(self, eng, job):
        n, words = job
        self.found.emit(n, [{**r, "label": r["about"], "hint": f'{r["seconds"]:g} s · {r["where"]}' if r.get("seconds")
                             else r["where"]} for r in sound_cues.choices(words, 40)])

    def describe(self, job, error):
        return error.line() if hasattr(error, "line") else f"Error: sounds: {error}"


class CuePick(QObject):
    changed = Signal()
    opened = Signal()               # QML opens the popover (the action's `do`)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._layer, self._words, self._rows, self._asked, self._got = bridge, "", "", [], 0, 0
        self._search = _Search("sound-search", self)
        self._search.found.connect(self._take)
        self._search.failed.connect(self._failed)
        self._search.start()

    layer = Property(str, lambda self: self._layer, notify=changed)
    words = Property(str, lambda self: self._words, notify=changed)
    sounds = Property("QVariantList", lambda self: self._rows, notify=changed)
    searching = Property(bool, lambda self: self._got < self._asked, notify=changed)

    @Property(str, notify=changed)
    def what(self):
        return self.b.label_of(self.b.doc.item(self._layer)) if self._layer and self.b.doc.has(self._layer) else ""

    @Slot(result=bool)
    def start(self):
        layers = self.b.selected_layers()
        if len(layers) != 1:
            self.b._set_status("Add a sound here: select one layer.")
            return False
        self._layer = layers[0]
        self.search(self._words)
        self.opened.emit()
        return True

    @Slot(str)
    def search(self, words):
        """Look for `words` off the screen's thread; the list shown stays until the newest answer arrives."""
        self._words, self._asked = words, self._asked + 1
        self._search.post_latest((self._asked, words))
        self.changed.emit()

    def _take(self, n, rows):
        self._got = max(self._got, n)
        if n == self._asked:                # an older search's answer is dropped: the newest words win
            self._rows = rows
        self.changed.emit()

    def _failed(self, line):
        """The library can't be read: said, never an empty list passed off as "no sounds match"."""
        self._got, self._rows = self._asked, []
        self.b._fail(line)
        self.changed.emit()

    def wait(self, timeout_s: float) -> bool:
        """For scripted steps: run the event loop until the newest search is in (False when it took too long)."""
        import time
        from PySide6.QtCore import QCoreApplication
        end = time.time() + timeout_s
        while self.searching and time.time() < end:
            QCoreApplication.processEvents()
            time.sleep(0.02)
        return not self.searching

    def close(self):
        self._search.close()

    @Slot(str, result=bool)
    def pick(self, path):
        """Tie `path` to the layer: one change in Sound's song (and its marker), said in the status line."""
        if not self._layer:
            return False
        try:
            about = next((r["about"] for r in self._rows if r["path"] == path), "")
            r = sound_cues.cue(self.b.doc.folder, self.b.doc, self._layer, path, self.b.who,
                               chosen=self.b.comp().get("soundtrack", ""), about=about)
        except Exception as e:  # noqa: BLE001  loud, in words
            self.b._fail(e.line() if hasattr(e, "line") else f"Error: Add a sound here: {e}")
            return False
        self.b._set_status(f'Added {about or Path(r["file"]).stem} at "{r["marker"]}" · RostrumSound mixes it · Ctrl+Z takes it back')
        self._layer = ""
        self.changed.emit()
        return True
