"""The render sheet (SPEC §11.2, mockup 08): Rostrum3D's fill of the kit's Export sheet (rostrum_gui/export_sheet.py;
rows: qml/ExportSettings3D.qml; the estimate: qml/RenderEstimate.qml and estimate_sheet.py). The ▾ beside
the header's Render and Ctrl+E open it (Render itself and F12 make the Final picture at once: render_job.py).

What: "This frame" (the playhead frame as a picture) or the shot (its frames: the whole shot or the stretch set on it).
Quality and Size are the shot's own render settings (render_fields): changing them here is a shot edit, one undo step,
saved on the shot, the same fields agents set and read. So are Save as (png, exr, or both) and, only while it saves an
EXR, the Passes row (its layers: Light, Shadow, Reflections, Masks per item, Depth, Surface direction). Both go through the SAME code the agents' tools use (rostrum3d.mcp.render: `still` for a frame; the same
folder, files, numbering and manifest for a sequence): a project render version `renders/<item>/vNNN/`, in the
background on its own engine process, so the picture exported is the one the Render button and render_still make.
Browse: the files are also copied into that folder (a sequence into a new folder there). A failure is words and the
bridge's red error, never a quiet "done".
"""
from __future__ import annotations

import shutil
import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import project
from rostrum_gui.edits import edit_label, field_call
from rostrum_gui.export_sheet import ExportSheet, free_path
from rostrum3d.compile import describe, shot_info
from rostrum3d.engine import Engine
from rostrum3d.mcp.estimate import scale
from rostrum3d.mcp.render import DocView, still
from rostrum3d.mcp.sequence import sequence
from rostrum3d.material_fields import any_stylized
from rostrum3d.render_fields import FORMATS, PASS_HELP, PASSES, QUALITIES, SIZES, engine_fields, settings

from .estimate_sheet import Estimate

FRAME, SHOT = "frame", "shot"
FORMAT_ROWS = [{"value": "png", "label": "PNG picture"}, {"value": "exr", "label": "EXR (for the Editor)"},
               {"value": "both", "label": "PNG and EXR"}]
QUALITY_ROWS = [{"value": q, "label": q.capitalize()} for q in QUALITIES]
STYLIZED_ROW = {"value": "stylized", "label": "Stylized"}       # offered while a material has Lines or Halftone on


class Export3D(ExportSheet):
    VERBS = ("Render", "Rendering", "Rendered")
    own = Signal()

    def __init__(self, bridge, make_engine=Engine, parent=None):
        super().__init__(bridge, parent)
        self.changed.connect(self.own)
        self._make_engine, self._engine, self._halt = make_engine, None, threading.Event()
        self._choice = FRAME
        self.estimate = Estimate(self, make_engine)
        bridge.frameChanged.connect(self.changed)       # the file's name follows the playhead
        bridge.pageChanged.connect(self._on_page)
        for signal in (self.changed, bridge.docChanged):   # any change: the number follows at once (or is measured again)
            signal.connect(self.estimate.refresh)

    @Property(str, constant=True)
    def sheetTitle(self):
        return "Render"

    @Property(QObject, constant=True)
    def timeEstimate(self):
        return self.estimate

    @Slot()
    def openFor(self):
        """The ▾ beside the header's Render / Ctrl+E: open on this frame on the Build page, on the shot on Animate and Render."""
        if not self.running():
            self._choice = FRAME if self.bridge.page == "build" else SHOT
            self.stale()
        self.setOpen(True)
        self.estimate.check_card()
        self.changed.emit()

    def wants_time(self) -> bool:
        """The time is shown: in the open sheet, or in the Render page's settings panel (the shot's settings, SPEC §11.3)."""
        return self.open or self.bridge.page == "render"

    def _on_page(self):
        """On the Render page the settings panel is the shown shot's render settings: what it renders is the shot."""
        if self.bridge.page == "render" and not self.running():
            self._choice = SHOT
            self.stale()
        self.changed.emit()

    # ---- the kit's questions ----------------------------------------------------------------------------
    def choices_list(self):
        n = self._frames()
        return [{"value": FRAME, "label": "This frame", "tip": "The picture at the playhead"},
                {"value": SHOT, "label": f'{self.bridge.shotInfo["label"]} · {n} frame{"s" * (n != 1)}',
                 "tip": "The shot's frames, as numbered pictures"}]

    def action_text(self):
        return "Render this frame" if self._choice == FRAME else f"Render {self._frames()} frames"

    def _frames(self) -> int:
        s = self._settings()
        return s["end"] - s["start"] + 1

    def replaceable(self):
        return self._choice == FRAME

    def _stem(self):
        return f'{self.bridge.doc.item_id or "doc"}_{self.bridge.shot_id}'

    def file_name(self):
        ext = self._settings()["formats"][0]
        return f"{self._stem()}_f{self.bridge.frame:04d}.{ext}" if self._choice == FRAME else f"{self._stem()}.{{frame}}.{ext}"

    def default_folder(self):
        doc = self.bridge.doc
        return str(project.next_render(doc.folder, doc.item_id)) if doc.folder and doc.item_id else "The render cache"

    def planned(self):
        if not self._folder:
            return None
        return Path(self._folder) / (self.file_name() if self._choice == FRAME else self._stem())   # a sequence: its own folder

    # ---- the shot's render settings (render_fields), read and set as agents do ---------------------------------
    def _shot(self) -> dict:
        return next(x for x in self.bridge.doc.data["shots"] if x["id"] == self.bridge.shot_id)

    def _settings(self, over: dict | None = None) -> dict:
        return settings({**self._shot(), **(over or {})}, shot_info(self.bridge.doc.data, self.bridge.shot_id))

    def plan_now(self, over: dict | None = None):
        """(scene, info, settings, frames) of what Render would make now: what the estimate measures and scales."""
        b = self.bridge
        info, s = shot_info(b.doc.data, b.shot_id), self._settings(over)
        if self._choice == FRAME:
            s["start"] = s["end"] = b.frame
        return describe(b.doc.data, b.shot_id, b.doc.folder), info, s, s["end"] - s["start"] + 1

    def gpu_ours(self) -> bool:
        """One of this window's renders is on the graphics card (the estimate waits, so it measures a free card)."""
        return self.running() or self.bridge.render.running() or self.bridge.queue.running()

    def fitting(self, m: dict, budget_s: float) -> list[dict]:
        """Over a budget: each lower quality preset, then half size, that alone fits (scaled from the same measurement)."""
        out, now = [], self._settings()
        tries = [("renderQuality", q, q.capitalize()) for q, v in QUALITIES.items() if v["samples"] < now["samples"]]
        if SIZES[self._shot().get("renderSize", "full")] > SIZES["half"]:
            tries.append(("renderSize", "half", "Size ½"))
        for field, value, word in tries:
            _, _, s, frames = self.plan_now({field: value})
            e = scale(m, s, frames, mp4=False)
            if e["seconds"] <= budget_s:
                out.append({"field": field, "value": value, "text": f'{word} · {e["text"].split(" · ")[0].lower()}'})
        return out

    @Property("QVariantList", notify=own)
    def qualities(self):
        """Draft · Good · Final, and Stylized while a material has Lines or Halftone on (or the shot is set to it)."""
        stylized = any_stylized(self.bridge.doc.data) or self._shot().get("renderQuality") == "stylized"
        return QUALITY_ROWS + ([STYLIZED_ROW] if stylized else [])

    @Property(str, notify=own)
    def quality(self):
        return self._settings()["quality"]

    @Property(str, notify=own)
    def qualityText(self):
        s = self._settings()
        if s["renderer"] == "stylized":
            return "Stylized renderer · drawn at twice the size for smooth edges"
        return f'{s["samples"]} samples' + (" · noise cleaned" if s["denoise"] else "")

    @Property("QVariantList", notify=own)
    def sizes(self):
        w, h = self.bridge.shotInfo["width"], self.bridge.shotInfo["height"]
        return [{"value": "full", "label": f"{w} × {h}"}, {"value": "half", "label": "½"}, {"value": "double", "label": "× 2"}]

    @Property(str, notify=own)
    def size(self):
        return self._shot().get("renderSize", "full")

    @Property(str, notify=own)
    def sizeText(self):
        s = self._settings()
        return f'{s["width"]} × {s["height"]}'

    @Slot(str, str)
    def setShot(self, field, value):
        """Quality or Size from the sheet: a change to the shot's render settings (one undo step, saved on the shot)."""
        b, sid = self.bridge, self.bridge.shot_id
        if self.running() or self._shot().get(field) == value:
            return
        b._guard(lambda: b._apply([field_call(b.doc, sid, field, value)], edit_label(b.doc, sid, field, value)))
        self.stale()
        self.changed.emit()

    # ---- its own settings ---------------------------------------------------------------------------------
    @Property("QVariantList", constant=True)
    def formats(self):
        return FORMAT_ROWS

    @Property(str, notify=own)
    def format(self):
        return self._shot().get("renderFormat", "png")

    @Slot(str)
    def setFormat(self, value):
        if value in FORMATS:
            self.setShot("renderFormat", value)

    @Property("QVariantList", notify=own)
    def passes(self):
        """The Passes row: only while the shot saves an EXR (absent for PNG, never greyed); Beauty is always in it."""
        if "exr" not in self._settings()["formats"] or self._settings()["renderer"] != "cycles":
            return []                  # the passes are Cycles' (a Stylized render's EXR is the picture alone)
        on = set(self._settings()["passes"])
        return [{"value": field, "label": label, "on": name in on, "help": PASS_HELP[name]} for name, (field, label, _) in PASSES.items()]

    @Slot(str, bool)
    def setPass(self, field, on):
        """A pass switched on or off: a change to the shot's render settings, like Quality (one undo step)."""
        b, sid = self.bridge, self.bridge.shot_id
        if self.running() or self._shot().get(field) == on:
            return
        b._guard(lambda: b._apply([field_call(b.doc, sid, field, on)], edit_label(b.doc, sid, field, on)))
        self.stale()
        self.changed.emit()

    # ---- the job ----------------------------------------------------------------------------------------------
    def begin(self, out, overwrite):
        b = self.bridge
        if b.render.running() or b.queue.running():
            raise RuntimeError("a render is already running; wait for it or cancel it first")
        scene, info, s, _ = self.plan_now()             # the shot's render settings: what the estimate measured
        info = {**info, "start": s["start"], "end": s["end"]}
        return {"info": info, "renderer": s["renderer"], "cycles": engine_fields(s), "scene": scene, "doc": DocView.of(b.doc),
                "frame": b.frame, "folder": b.doc.folder, "out": out, "size": (s["width"], s["height"]),
                "shot": self._choice == SHOT, "formats": s["formats"], "passes": s["passes"], "stem": self._stem(),
                "main": s["formats"][0]}

    def work(self, plan, progress):
        self._halt = halt = threading.Event()
        engine = self._engine = self._make_engine()
        try:
            if halt.is_set():
                raise RuntimeError("Export cancelled")
            done, files = (self._sequence if plan["shot"] else self._frame)(plan, engine, progress, halt.is_set)
            if plan["out"] is not None:
                files = self._copy(plan, files)
            first = files[0]
            file = first.with_name(f"{first.name.rsplit('.', 2)[0]}.{{frame}}{first.suffix}") if plan["shot"] else first
            return {"files": [str(f) for f in files], "file": str(file), "version": done.name}
        finally:
            self._engine = None
            engine.close()

    @staticmethod
    def _frame(plan, engine, progress, stopped):
        done, files, _ = still("export", plan["doc"], plan["info"], plan["scene"], engine, plan["frame"], plan["renderer"],
                               plan["size"], plan["formats"], 0, plan["cycles"], plan["folder"], plan["passes"], stopped)
        return done, files

    @staticmethod
    def _sequence(plan, engine, progress, stopped):
        return sequence("export", plan["doc"], plan["info"], plan["scene"], engine, plan["size"], plan["formats"],
                        plan["cycles"], plan["folder"], plan["stem"], lambda i, n: progress(i / max(n, 1)), plan["passes"], stopped,
                        renderer=plan["renderer"])

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
        self.estimate.close()
        self.stop()
