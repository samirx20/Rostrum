"""Rostrum3D's fill of the kit's Export sheet (rostrum_gui/export_sheet.py, EXPORT.md; settings: qml/ExportSettings3D.qml).

What: "This frame" (the playhead frame as a picture) or "The whole shot" (every frame as a numbered picture). File: png,
exr, or both. Both go through the SAME code the agents' tools use (rostrum3d.mcp.render: `still` for a frame; the same
folder, files, numbering and manifest for a sequence): a project render version `renders/<item>/vNNN/`, in the
background on its own engine process, so the picture exported is the one the Render button and render_still make.
Browse: the files are also copied into that folder (a sequence into a new folder there). A failure is words and the
bridge's red error, never a quiet "done".
"""
from __future__ import annotations

import shutil
import threading
from pathlib import Path

from PySide6.QtCore import Property, Signal, Slot
from rostrum_core import project
from rostrum_gui.export_sheet import ExportSheet, free_path
from rostrum3d.compile import describe, shot_info
from rostrum3d.engine import Engine
from rostrum3d.mcp import draw
from rostrum3d.mcp.render import FIRST, DocView, _finish, _folder, _manifest, _renumber, still

from .render_job import SETTINGS

FRAME, SHOT = "frame", "shot"
FORMATS = {"png": ["png"], "exr": ["exr"], "both": ["png", "exr"]}
FORMAT_ROWS = [{"value": "png", "label": "PNG picture"}, {"value": "exr", "label": "EXR (for the Editor)"},
               {"value": "both", "label": "PNG and EXR"}]


class Export3D(ExportSheet):
    own = Signal()

    def __init__(self, bridge, make_engine=Engine, parent=None):
        super().__init__(bridge, parent)
        self.changed.connect(self.own)
        self._make_engine, self._engine, self._halt = make_engine, None, threading.Event()
        self._choice, self._format = FRAME, "png"
        bridge.frameChanged.connect(self.changed)       # the file's name follows the playhead

    # ---- the kit's questions ----------------------------------------------------------------------------
    def choices_list(self):
        return [{"value": FRAME, "label": "This frame", "tip": "The picture at the playhead"},
                {"value": SHOT, "label": "The whole shot", "tip": "Every frame, as numbered pictures"}]

    def replaceable(self):
        return self._choice == FRAME

    def _stem(self):
        return f'{self.bridge.doc.item_id or "doc"}_{self.bridge.shot_id}'

    def file_name(self):
        ext = FORMATS[self._format][0]
        return f"{self._stem()}_f{self.bridge.frame:04d}.{ext}" if self._choice == FRAME else f"{self._stem()}.{{frame}}.{ext}"

    def default_folder(self):
        doc = self.bridge.doc
        return str(project.next_render(doc.folder, doc.item_id)) if doc.folder and doc.item_id else "The render cache"

    def planned(self):
        if not self._folder:
            return None
        return Path(self._folder) / (self.file_name() if self._choice == FRAME else self._stem())   # a sequence: its own folder

    # ---- its own settings ---------------------------------------------------------------------------------
    @Property("QVariantList", constant=True)
    def formats(self):
        return FORMAT_ROWS

    @Property(str, notify=own)
    def format(self):
        return self._format

    @Slot(str)
    def setFormat(self, value):
        if value in FORMATS and not self.running():
            self._format = value
            self.stale()
            self.changed.emit()

    # ---- the job ----------------------------------------------------------------------------------------------
    def begin(self, out, overwrite):
        b = self.bridge
        if b.render.running():
            raise RuntimeError("a render is already running; wait for it or cancel it first")
        info = dict(shot_info(b.doc.data, b.shot_id))
        return {"info": info, "scene": describe(b.doc.data, b.shot_id, b.doc.folder), "doc": DocView.of(b.doc),
                "frame": b.frame, "folder": b.doc.folder, "out": out, "size": (info["width"], info["height"]),
                "shot": self._choice == SHOT, "formats": FORMATS[self._format], "stem": self._stem(),
                "main": FORMATS[self._format][0]}

    def work(self, plan, progress):
        self._halt = halt = threading.Event()
        engine = self._engine = self._make_engine()
        try:
            if halt.is_set():
                raise RuntimeError("Export cancelled")
            done, files = (self._sequence if plan["shot"] else self._frame)(plan, engine, progress)
            if plan["out"] is not None:
                files = self._copy(plan, files)
            first = files[0]
            file = first.with_name(f"{first.name.rsplit('.', 2)[0]}.{{frame}}{first.suffix}") if plan["shot"] else first
            return {"files": [str(f) for f in files], "file": str(file), "version": done.name}
        finally:
            self._engine = None
            engine.close()

    @staticmethod
    def _frame(plan, engine, progress):
        done, files, _ = still("export", plan["doc"], plan["info"], plan["scene"], engine, plan["frame"], "cycles",
                               plan["size"], plan["formats"], 0, SETTINGS, plan["folder"])
        return done, files

    @staticmethod
    def _sequence(plan, engine, progress):
        info, doc, name = plan["info"], plan["doc"], plan["stem"]
        f0, f1, (w, h) = info["start"], info["end"], plan["size"]
        partial, is_version = _folder(plan["folder"], doc, info)
        req = {e: str(partial / f"{name}.{{frame}}.{e}") for e in plan["formats"]}
        draw.render("export", f"frames {f0}-{f1} of {info['id']}", engine, plan["scene"], camera=info["camera"],
                    renderer="cycles", frames=[f0, f1], width=w, height=h, exposure=0, timeoutS=3600, **SETTINGS,
                    progress=lambda i, n, _=None: progress(i / max(n, 1)), **req)
        for e in plan["formats"]:
            _renumber(partial, name, e, f0, FIRST)
        want = (f1 - f0 + 1) * len(plan["formats"])
        made = sorted(p for e in plan["formats"] for p in partial.glob(f"{name}.*.{e}"))
        if len(made) != want or any(p.stat().st_size == 0 for p in made):      # fail loudly: the .partial stays
            raise RuntimeError(f"the shot's frames came out as {len(made)} files, expected {want}; they are left in {partial}")
        done = _finish(partial, is_version, _manifest(doc.item_id, doc, info, partial, "cycles", (w, h),
                                                      list(range(f0, f1 + 1)), [p.name for p in made], FIRST))
        return done, [done / p.name for p in made]

    @staticmethod
    def _copy(plan, files):
        """Browse: the same files, copied there (a picture under the chosen name; a sequence into its own new folder)."""
        out = plan["out"]
        if plan["shot"]:
            dest = free_path(out)
            dest.mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.copyfile(f, dest / f.name)
            return [dest / f.name for f in files]
        out.parent.mkdir(parents=True, exist_ok=True)
        copied = []
        for f in files:
            target = out if f.suffix == f".{plan['main']}" else out.with_suffix(f.suffix)
            shutil.copyfile(f, target)
            copied.append(target)
        return sorted(copied, key=lambda p: p != out)

    def stop(self):
        self._halt.set()
        engine = self._engine
        if engine is not None and engine.proc is not None and engine.proc.poll() is None:
            engine.proc.kill()                          # our own child, by its handle

    def close(self):
        self.stop()
