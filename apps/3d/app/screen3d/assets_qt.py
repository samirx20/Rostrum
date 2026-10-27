"""The asset library sheet, for QML as `backend.assets` (qml/AssetSheet.qml; Import › Asset library opens it).

The sources (rostrum3d.assets) with their switches: off until the person switches one on (saved in their settings;
a scripted run's go to its scratch home). An off source shows nothing more and is never asked anything. With one on:
a search field and a grid of its models; thumbnails are fetched as tiles show (cached in the user cache folder). A
click on a model downloads it into the project folder (progress on its tile) and imports it on the surface under the
view's centre (importing.py's importAtCentre: one `import.add`, one undo step). Every network call runs on a worker
thread; results come back through a signal, on the GUI thread.
"""
from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum3d import assets
from rostrum3d.assets import settings, thumbs

THUMB_WORKERS = 3          # thumbnails fetched at once
PROGRESS_S = 0.1            # a tile's progress is redrawn at most this often
# The layout check's fixed offline list (never the network): long names included.
SAMPLE = [{"id": f"sample_{n}", "name": name, "thumb_url": "", "by": ""} for n, name in enumerate(
    ["Arm Chair 01", "Wooden Crate", "Potted Plant with a very long name that has to be cut short", "Brass Lamp",
     "Marble Bust", "Tea Set", "Old Radio", "Stool"])]


class Assets(QObject):
    changed = Signal()
    tilesChanged = Signal()
    landed = Signal(object)                 # (what, payload) from a worker thread

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b = bridge
        self._shown, self._browse, self._query, self._page = False, "", "", 0
        self._models: list[dict] = []
        self._more, self._busy, self._line, self._sample = False, False, "", False
        self._thumbs: dict[str, str] = {}       # model id -> file URL of its thumbnail
        self._getting: dict[str, float] = {}    # model id -> download progress 0..1
        self._asked: set[str] = set()
        self._seen = 0.0
        self._thumb_queue, self._thumb_workers = queue.Queue(), 0
        self.landed.connect(self._on_landed)

    # ---- what the sheet shows ----------------------------------------------------------------------------------
    shown = Property(bool, lambda self: self._shown, notify=changed)
    browsing = Property(str, lambda self: self._browse, notify=changed)    # the on source whose models show
    query = Property(str, lambda self: self._query, notify=changed)
    models = Property("QVariantList", lambda self: self._models, notify=changed)
    hasMore = Property(bool, lambda self: self._more, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)         # a search under way
    line = Property(str, lambda self: self._line, notify=changed)          # what failed, or "nothing found"
    thumbs = Property("QVariantMap", lambda self: self._thumbs, notify=tilesChanged)
    getting = Property("QVariantMap", lambda self: self._getting, notify=tilesChanged)

    @Property("QVariantList", notify=changed)
    def sources(self):
        return [{**f, "on": f["on"] or (self._sample and f["id"] == "polyhaven")}
                for f in (assets.facts(s) for s in assets.sources())]

    @Property("QVariantList", notify=changed)
    def onSources(self):
        return [{"value": s["id"], "label": s["name"]} for s in self.sources if s["on"]]

    # ---- the person's actions ----------------------------------------------------------------------------------
    @Slot()
    def open(self):
        self._shown = True
        self._pick_browse()
        self.changed.emit()

    @Slot()
    def close(self):
        self._shown = False
        self.changed.emit()

    @Slot(str, bool)
    def setOn(self, source_id, on):
        settings.set_on(source_id, on)
        self._pick_browse(source_id if on else "")

    @Slot(str)
    def browse(self, source_id):
        self._pick_browse(source_id)

    @Slot(str)
    def search(self, text):
        self._query = text.strip()
        self._run_search(0)

    @Slot()
    def more(self):
        self._run_search(self._page + 1)

    @Slot(str)
    def wantThumb(self, model_id):
        """A tile came into view: its thumbnail, once (lazy: tiles never shown cost nothing)."""
        m = next((m for m in self._models if m["id"] == model_id), None)
        if self._sample or m is None or model_id in self._asked or not m.get("thumb_url"):
            return
        self._asked.add(model_id)
        src = self._browse
        cached = thumbs.cached(src, model_id)
        if cached.is_file():
            return self._on_landed(("thumb", (model_id, cached)))
        self._thumb_queue.put((src, model_id, m["thumb_url"]))
        while self._thumb_workers < THUMB_WORKERS:
            self._thumb_workers += 1
            threading.Thread(target=self._thumb_worker, daemon=True, name="asset-thumbs").start()

    @Slot(str)
    def bringIn(self, model_id):
        """A model clicked: download it into the project (or reuse it) and import it under the view's centre."""
        if model_id in self._getting:
            return
        if self._sample:
            return self.b.fail_line("Error: asset library: this is the layout check's sample list; nothing to bring in.")
        src, project = self._browse, self._project()
        self._getting[model_id] = 0.0
        self.tilesChanged.emit()

        def step(fraction):
            if time.monotonic() - self._seen >= PROGRESS_S:
                self._seen = time.monotonic()
                self.landed.emit(("progress", (model_id, fraction)))
        self._work(lambda: ("file", (model_id, assets.bring_in(src, model_id, project, step))), model_id=model_id)

    def use_sample(self):
        """The layout check: Poly Haven shown on (in this sheet only: the check's runs share one settings home) with a
        fixed offline list; no network."""
        self._sample = True
        self._shown, self._browse, self._models, self._more, self._line = True, "polyhaven", list(SAMPLE), True, ""
        self.changed.emit()

    # ---- inside ------------------------------------------------------------------------------------------------
    def _project(self):
        return self.b.doc.folder or None               # the sample or a scratch scene has none: bring_in says so

    def _pick_browse(self, prefer=""):
        on = [s.id for s in assets.sources() if settings.is_on(s.id)]
        pick = prefer if prefer in on else self._browse if self._browse in on else (on[0] if on else "")
        if pick != self._browse or (pick and not self._models and not self._busy):
            self._browse, self._models, self._thumbs, self._asked = pick, [], {}, set()
            self._line, self._more, self._busy = "", False, False      # a search of the last source is dropped when it lands
            if pick and not self._sample:
                self._run_search(0)
        self.changed.emit()

    def _run_search(self, page):
        if not self._browse or self._sample:
            return
        src, query = self._browse, self._query
        self._busy, self._line = True, ""
        if page == 0:
            self._models, self._thumbs, self._asked = [], {}, set()
        self.changed.emit()
        self._work(lambda: ("found", (src, query, page, assets.search(src, query, page))))

    def _thumb_worker(self):
        while True:
            src, model_id, url = self._thumb_queue.get()
            try:
                self.landed.emit(("thumb", (model_id, thumbs.fetch(src, model_id, url))))
            except Exception:  # noqa: BLE001  a missing thumbnail leaves its tile plain; the model still comes in
                pass

    def _work(self, fn, quiet=False, model_id=None):
        def run():
            try:
                self.landed.emit(fn())
            except assets.AssetError as e:
                self.landed.emit(("failed", (model_id, "" if quiet else str(e))))
            except Exception as e:  # noqa: BLE001  loud on the sheet's line, never a silent stop
                self.landed.emit(("failed", (model_id, "" if quiet else f"{type(e).__name__}: {e}")))
        threading.Thread(target=run, daemon=True, name="asset-library").start()

    def _on_landed(self, answer):
        what, data = answer
        if what == "found":
            src, query, page, found = data
            if (src, query) != (self._browse, self._query):
                return                                     # an older search: the person moved on
            self._models = self._models + found if page else found
            self._page, self._more, self._busy = page, len(found) > 0 and len(found) >= 40, False
            self._line = "" if self._models else ("Nothing matches those words." if query else "No models here.")
            self.changed.emit()
        elif what == "thumb":
            model_id, path = data
            if path is not None:
                self._thumbs = {**self._thumbs, model_id: QUrl.fromLocalFile(str(path)).toString()}
                self.tilesChanged.emit()
        elif what == "progress":
            model_id, fraction = data
            if model_id in self._getting:
                self._getting = {**self._getting, model_id: fraction}
                self.tilesChanged.emit()
        elif what == "file":
            model_id, path = data
            self._drop(model_id)
            self.b._importer.importAtCentre(str(Path(path)))
        elif what == "failed":
            model_id, line = data
            self._drop(model_id)
            if line:
                self._busy, self._line = False, line
                self.changed.emit()
                self.b.fail_line(f"Error: asset library: {line}")

    def _drop(self, model_id):
        if model_id in self._getting:
            self._getting = {k: v for k, v in self._getting.items() if k != model_id}
            self.tilesChanged.emit()

