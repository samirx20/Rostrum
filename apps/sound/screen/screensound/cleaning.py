"""The "Make cleaned take" button of a clip (Timeline inspector): shown only while the selected clip has a cleanup step
set and its cleaned take is not made yet. Pressing it runs the same job as the MCP `render_cleanup`
(`rostrum_sound.clean_clips.make_clips`) in the background; the status line follows its progress and a failure is
written in words (and is the bridge's red error), never a quiet "done". Exposed to QML as `mixer.cleaning`. The
"Clean up…" opens the Cleanup group; the job starts the same way for every selected clip (`makeFor`)
whether the clean-up models are on this computer.
Making a take never edits the document (it lives in the cache); the sound is re-rendered once it is made.
The job runs in its own process (clean_process.py): `cancel` ends it, nothing half-made is kept, and the clips that
were being cleaned play their originals (`useCleaned` off, one undo step). Once a take is made, `info` gives the
"did it help?" line (clean_measure.py: measured once per take, kept) for the clean-up bar.
"""
from __future__ import annotations

import copy
import threading

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_sound import cleanup
from rostrum_sound.doc import media
from rostrum_sound.cleanup import fetch

from . import inspect, voice_actions as V
from .clean_measure import Measures
from .clean_process import CleanProcess
from .model_fetch import ModelFetch


PENDING = "The cleaned take is not made yet: the clip plays its original until it is."


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
        self._demo: dict = {}
        self._job: CleanProcess | None = None        # the clean-up job's process while it runs (Cancel ends it)
        self._measure = Measures(self)                # "Did it help?": measured once per take
        self._measure.changed.connect(self.changed)
        self._download = ModelFetch(self)         # asked first when a step needs a model that is not installed
        self._recipes: dict[str, str] = {}        # clip id -> the clean-up it had when last looked at (a change = made on release)
        self._pending: list[str] = []             # the clips a download was asked for (made once it lands)
        self._steps: dict[str, list] = {}         # clip id -> [progress notes seen, notes expected] while making
        self._download.ready.connect(lambda: self.makeFor(self._pending or [self._clip]))
        self._download.cancelled.connect(self._note_cancelled)
        self._progress.connect(self._note)
        self._done.connect(self._finish)
        bridge.selectedItemsChanged.connect(self._check)
        bridge.docChanged.connect(self._on_release)
        bridge.docChanged.connect(self._check)
        bridge.selectedItemsChanged.connect(self.changed)
        bridge.docChanged.connect(self.changed)
        self._on_release()
        self._check()

    @Property(str, notify=changed)
    def clip(self):
        """The selected clip's id while it needs its cleaned take made ("" otherwise: the button is absent)."""
        return self._clip

    @Property("QVariantMap", notify=changed)
    def progress(self):
        """{clip id: 0..1} while their cleaned takes are being made (the arrangement fills each clip left to right)."""
        return {i: min(0.95, seen / total) for i, (seen, total) in self._steps.items()}

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(QObject, constant=True)
    def download(self):
        return self._download

    @Property("QVariantMap", notify=changed)
    def audition(self):
        """{show, after}: the Before | After switch (Editor header, Clean up group) shows while every selected clip has a
        clean-up set (and, to go to After, its take is made); `after` = the cleaned take is the one playing."""
        f = self.bridge._facts()
        show = bool(f.ids) and V.ba_valid(f)
        return {"show": show, "after": show and not all(it.get("useCleaned", True) is False for it in f.items)}

    @Slot(result=bool)
    def flip(self):
        """Before / After (H): `clip.set {useCleaned}` on the selected clips: one step, playback goes on."""
        return bool(self.bridge.run("before_after"))

    @Slot(result=bool)
    def make(self):
        if self._clip:
            return self.makeFor([self._clip])
        self._status = self._why_nothing()      # never a quiet "did not start": say why there is nothing to make
        self.changed.emit()
        return False

    def _why_nothing(self) -> str:
        sel, doc = self.bridge.selected, self.bridge.doc
        if self._busy:
            return "A cleaned take is already being made."
        if sel and doc.has(sel) and doc.item(sel)["type"] == "clip":
            return ("The cleaned take is already made." if cleanup.recipe_of(doc.item(sel))
                    else "This clip has no clean-up step on: turn on Less noise, Less echo or Dialogue only first.")
        return "Select a clip with a clean-up step to make its cleaned take."

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
        self._steps = {i: [0, 1 + len(cleanup.recipe_of(doc.item(i)))] for i in ids}
        self._status = f"Making the cleaned take{'s' if len(ids) > 1 else ''}…"
        self.changed.emit()
        snapshot = copy.deepcopy(doc.data)                  # the worker reads a copy: edits go on meanwhile
        self._job = CleanProcess(snapshot, doc.folder, ids, self._progress.emit)
        self._thread = threading.Thread(target=lambda job=self._job: self._done.emit(job.run()), daemon=True)
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
        if self._job is not None:
            self._job.kill()                        # closing the app ends the job: nothing half-made is kept
        if self._thread is not None:
            self._thread.join(timeout=600)

    @Property(bool, notify=changed)
    def cancellable(self):
        """A clean-up is running and has not been told to stop: the Cancel button shows only then."""
        return self._busy and self._job is not None and not self._job.cancelled

    @Slot()
    def cancel(self):
        """Stop a running clean-up (the job's process is ended, no take is kept; see _finish): the clips being cleaned
        play their originals. A job that will not stop is a red error, never a quiet carry-on."""
        if not self.cancellable:
            return
        try:
            self._job.kill()
        except OSError as e:
            return self.bridge._fail(f"Error: cleaned take: could not stop the clean-up ({e}).")
        self._status = "Stopping the clean-up…"
        self.changed.emit()

    def _note(self, text):
        clip = text.split(":", 1)[0]
        if clip in self._steps:
            self._steps[clip][0] += 1
        self._status = inspect.in_words(text, self.bridge.doc)
        self.changed.emit()

    def _finish(self, error):
        ids, cancelled = list(self._steps), self._job is not None and self._job.cancelled
        self._busy, self._steps, self._job = False, {}, None
        self._status = error = inspect.in_words(error, self.bridge.doc)
        if cancelled:
            self._status = self._back_to_originals(ids)
        elif error:
            self.bridge._fail(error)
        else:
            for i in ids:
                self._measure.forget(i)                   # a take was just made: measure it once
            self.bridge._rebuild()                        # draw the cleaned take's waveform (the clip shows what it plays)
            self.bridge.transport.changed()               # play the cleaned take: render again
        self.changed.emit()
        self._check()

    def _back_to_originals(self, ids) -> str:
        """After Cancel: a clip still without its take plays its original (`useCleaned` off, one undo step), so Play
        never hits "take not made yet"; its settings stay and Make cleaned take tries again."""
        doc = self.bridge.doc
        todo = [i for i in ids if doc.has(i) and cleanup.needs_cleanup(doc.item(i))
                and cleanup.cached(media.file(doc.item(i)["media"]), cleanup.recipe_of(doc.item(i))) is None]
        if todo:
            self.bridge._guard(lambda: self.bridge._apply(
                [{"op": "clip.set", "target": todo, "args": {"useCleaned": False}}], "Play the original"))
        return "Cancelled. No cleaned take was made; the clip plays its original. Make cleaned take tries again."

    @Property("QVariantMap", notify=changed)
    def info(self):
        """{line, warn} for the selected clip's made take ("Background noise −18 dB · voice level unchanged"):
        measured once per take (clean_measure), {} while there is nothing to say."""
        sel, doc = self.bridge.selected, self.bridge.doc
        if self._demo:
            return self._demo
        if not (sel and doc.has(sel) and doc.item(sel)["type"] == "clip") or self._clip == sel:
            return {}
        c = doc.item(sel)
        recipe = cleanup.recipe_of(c)
        return self._measure.of(sel, media.file(c["media"]), recipe) if recipe and not self._busy else {}

    def demo(self, line: str, warn: str = "", status: str = ""):
        """The layout check's seam: show this result line / warning (and a status) as if measured."""
        self._demo, self._status = {"line": line, "warn": warn}, status
        self.changed.emit()

    @Property(bool, notify=changed)
    def shown(self):
        """The Clean up bar shows: a take to make, a job running (with Cancel), a result line or a note to say."""
        return bool(self._clip or self._busy or self._status or self.info.get("line"))

    def _on_release(self):
        """Made on release (DESIGN.md §3.10 step 3): a slider let go or a switch flipped changes a selected clip's
        clean-up, and its cleaned take starts at once (from the cache when it was made before: undo / redo / back to an
        earlier value are instant). A clip seen for the first time just records its clean-up."""
        doc, now, changed = self.bridge.doc, {}, []
        for t in doc.data.get("tracks", []):
            for c in t.get("clips", []):
                r = cleanup.recipe_of(c)
                now[c["id"]] = key = str(sorted(r.items()))
                if r and c["id"] in self._recipes and self._recipes[c["id"]] != key and c["id"] in self.bridge._picks.ids:
                    changed.append(c["id"])
        self._recipes = now
        if changed:
            self.makeFor(changed)

    def _check(self):
        sel, doc, clip = self.bridge.selected, self.bridge.doc, ""
        if sel and doc.has(sel) and doc.item(sel)["type"] == "clip":
            c = doc.item(sel)
            recipe = cleanup.recipe_of(c)
            key = (media.file(c["media"]), str(sorted(recipe.items())))
            if recipe and key not in self._made:
                if cleanup.cached(media.file(c["media"]), recipe) is None:
                    clip = sel
                else:
                    self._made.add(key)
        if clip != self._clip:
            self._clip = clip
            if not self._busy:
                self._status = PENDING if clip else ""
            self.changed.emit()
