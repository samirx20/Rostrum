"""The "Make cleaned take" button of a clip (Timeline inspector): shown only while the selected clip has a cleanup step
set and its cleaned take is not made yet. Pressing it runs the same job as the MCP `render_cleanup`
(`rostrum_sound.clean_clips.make_clips`) in the background; the status line follows its progress and a failure is
written in words (and is the bridge's red error), never a quiet "done". Exposed to QML as `mixer.cleaning`. The
context bar's "Clean up…" popover starts the same job for every selected clip (`makeFor`) and asks `missingWords`
whether the clean-up models are on this computer.
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
        self._pending: list[str] = []             # the clips a download was asked for (made once it lands)
        self._download.ready.connect(lambda: self.makeFor(self._pending or [self._clip]))
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
        return self.makeFor([self._clip] if self._clip else [])

    @Slot("QVariantList", result=bool)
    def makeFor(self, ids):
        """The cleaned takes of these clips (those with a clean-up step set), one job in the background."""
        doc = self.bridge.doc
        ids = [i for i in ids if doc.has(i) and doc.item(i)["type"] == "clip" and cleanup.recipe_of(doc.item(i))]
        if self._busy or not ids or self._download.state in ("asking", "downloading"):
            return False
        missing = []
        for i in ids:
            missing += [m for m in fetch.needed(cleanup.recipe_of(doc.item(i))) if m not in missing]
        if missing:                                         # ask before the first download; "Download" carries on
            self._status, self._pending = "", list(ids)     # a new question: an old "cancelled" line no longer holds
            self.changed.emit()
            self._download.ask(missing)
            return False
        self._busy, self._pending = True, []
        self._status = f"Making the cleaned take{'s' if len(ids) > 1 else ''}…"
        self.changed.emit()
        snapshot = copy.deepcopy(doc.data)                  # the worker reads a copy: edits go on meanwhile
        self._thread = threading.Thread(target=self._work, args=(snapshot, ids), daemon=True)
        self._thread.start()
        return True

    @Slot(bool, bool, bool, result=str)
    def missingWords(self, voice, noise, echo):
        """One sentence when the chosen steps need models not on this computer yet ("" when all are here)."""
        recipe = {"isolate": voice, "denoise": 0.6 if noise else 0, "dereverb": 0.6 if echo else 0}
        missing = fetch.needed({k: v for k, v in recipe.items() if v})
        if not missing:
            return ""
        mb = sum(m.size for m in missing) / 1e6
        return ("The clean-up models aren't on this computer yet: Clean downloads them first"
                + (f" (about {mb:.0f} MB)." if mb else "."))

    def _note_cancelled(self):
        self._status = "Download cancelled: the cleaned take is not made."
        self.changed.emit()

    def close(self):
        self._download.close()
        if self._thread is not None:
            self._thread.join(timeout=600)

    def _work(self, root, clip_ids):
        try:
            clean_clips.make_clips(root, clip_ids, progress=self._progress.emit)
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
