"""The "Make cleaned take" button of a clip (Timeline inspector): shown only while the selected clip has a cleanup step
set and its cleaned take is not made yet. Pressing it runs the same job as the MCP `render_cleanup`
(`rostrum_sound.clean_clips.make_clips`) in the background; the status line follows its progress and a failure is
written in words (and is the bridge's red error), never a quiet "done". Exposed to QML as `mixer.cleaning`.
Making a take never edits the document (it lives in the cache); the sound is re-rendered once it is made.
"""
from __future__ import annotations

import copy
import threading

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_sound import clean_clips, cleanup
from rostrum_sound.cleanup import fetch

from .model_fetch import ModelFetch


class CleanedTake(QObject):
    changed = Signal()
    _progress = Signal(str)
    _done = Signal(str)                       # "" = made, else the error line (from the worker thread)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._clip, self._busy, self._status = "", False, ""
        self._made: set = set()               # (media, recipe) already known to be in the cache
        self._thread: threading.Thread | None = None
        self._download = ModelFetch(self)         # asked first when a step needs a model that is not installed
        self._download.ready.connect(self.make)
        self._download.cancelled.connect(self._note_cancelled)
        self._progress.connect(self._note)
        self._done.connect(self._finish)
        bridge.selectionChanged.connect(self._check)
        bridge.docChanged.connect(self._check)
        self._check()

    @Property(str, notify=changed)
    def clip(self):
        """The selected clip's id while it needs its cleaned take made ("" otherwise: the button is absent)."""
        return self._clip

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(QObject, constant=True)
    def download(self):
        return self._download

    @Slot(result=bool)
    def make(self):
        if self._busy or not self._clip or self._download.state in ("asking", "downloading"):
            return False
        missing = fetch.needed(cleanup.recipe_of(self.bridge.doc.item(self._clip)))
        if missing:                                         # ask before the first download; "Download" carries on
            self._status = ""                               # a new question: an old "cancelled" line no longer holds
            self.changed.emit()
            self._download.ask(missing)
            return False
        self._busy, self._status = True, "Making the cleaned take…"
        self.changed.emit()
        snapshot = copy.deepcopy(self.bridge.doc.data)          # the worker reads a copy: edits go on meanwhile
        self._thread = threading.Thread(target=self._work, args=(snapshot, self._clip), daemon=True)
        self._thread.start()
        return True

    def _note_cancelled(self):
        self._status = "Download cancelled: the cleaned take is not made."
        self.changed.emit()

    def close(self):
        self._download.close()
        if self._thread is not None:
            self._thread.join(timeout=600)

    def _work(self, root, clip_id):
        try:
            clean_clips.make_clips(root, [clip_id], progress=self._progress.emit)
            err = ""
        except Exception as e:  # noqa: BLE001  shown on the screen, whatever it was
            err = f"Error: cleaned take: {getattr(e, 'line', lambda: e)()}"
        self._done.emit(err)

    def _note(self, text):
        self._status = text
        self.changed.emit()

    def _finish(self, error):
        self._busy = False
        self._status = error
        if error:
            self.bridge._fail(error)
        else:
            self.bridge.transport.changed()               # play the cleaned take: render again
        self.changed.emit()
        self._check()

    def _check(self):
        sel, doc, clip = self.bridge.selected, self.bridge.doc, ""
        if sel and doc.has(sel) and doc.item(sel)["type"] == "clip":
            c = doc.item(sel)
            recipe = cleanup.recipe_of(c)
            key = (c["media"], str(sorted(recipe.items())))
            if recipe and key not in self._made:
                if cleanup.cached(c["media"], recipe) is None:
                    clip = sel
                else:
                    self._made.add(key)
        if clip != self._clip:
            self._clip = clip
            if not self._busy:
                self._status = ""
            self.changed.emit()
