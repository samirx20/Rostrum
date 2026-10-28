"""The render sheet (SPEC §11.2, mockup 08): Rostrum3D's fill of the kit's Export sheet (rostrum_gui/export_sheet.py;
rows: qml/ExportSettings3D.qml; the estimate: qml/RenderEstimate.qml and estimate_sheet.py). The ▾ beside
the header's Render and Ctrl+E open it (Render itself and F12 make the Final picture at once: render_job.py).

What: "This frame" (the playhead frame as a picture), the shot (its frames: the whole shot or the stretch set on it, as
numbered pictures) or the shot as an MP4 video (H.264, plus a small `<name>-share.mp4`; the same code as render_video).
Quality and Size are the shot's own render settings (render_fields): changing them here is a shot edit, one undo step,
saved on the shot, the same fields agents set and read. So are Save as (png, exr, or both) and, only while it saves an
EXR, the Passes row (its layers: Light, Shadow, Reflections, Masks per item, Depth, Surface direction). Both go through the SAME code the agents' tools use (rostrum3d.mcp.render: `still` for a frame; the same
folder, files, numbering and manifest for a sequence): a project render version `renders/<item>/vNNN/`, in the
background on its own engine process, so the picture exported is the one the Render button and render_still make.
Browse: the files are also copied into that folder (a sequence into a new folder there). A failure is words and the
bridge's red error, never a quiet "done". While the shot renders the note says "Frame 12 of 120 · about 4 min left". A stopped or failed shot
render keeps the frames it finished: the sheet then says "Continues from 130 finished frames" (`resumeLine`) and Render
draws only the missing ones (rostrum3d.mcp.resume), as long as nothing rendered has changed.
"""
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import project
from rostrum_gui.edits import edit_label, field_call
from rostrum_gui.export_sheet import ExportSheet, free_path
from rostrum3d.compile import describe, shot_info
from rostrum3d.engine import Engine
from rostrum3d.mcp.estimate import scale
from rostrum3d.mcp import resume
from rostrum3d.mcp.render import DocView, check_ffmpeg, still, video, video_key
from rostrum3d.mcp.render import kept_count as video_kept
from rostrum3d.mcp.sequence import kept_count, sequence, sequence_key
from rostrum3d.material_fields import any_stylized
from rostrum3d.render_fields import FORMATS, PASS_HELP, PASSES, QUALITIES, SIZES, engine_fields, settings

from .estimate_sheet import Estimate
from .render_guess import words_left

FRAME, SHOT, VIDEO = "frame", "shot", "video"
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
        self._done_frames = 0                             # frames of the running shot finished so far (kept on a stop)
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
            self._choice = FRAME if self.bridge.page == "build" else SHOT if self._choice == FRAME else self._choice
            self.stale()
        self.setOpen(True)
        self.estimate.check_card()
        self.changed.emit()

    def wants_time(self) -> bool:
        """The time is shown: in the open sheet, or in the Render page's settings panel (the shot's settings, SPEC §11.3)."""
        return self.open or self.bridge.page == "render"

    def _on_page(self):
        """On the Render page the settings panel is the shown shot's render settings: what it renders is the shot."""
        if self.bridge.page == "render" and not self.running() and self._choice == FRAME:
            self._choice = SHOT
            self.stale()
        self.changed.emit()

    # ---- the kit's questions ----------------------------------------------------------------------------
    def choices_list(self):
        n, label = self._frames(), self.bridge.shotInfo["label"]
        return [{"value": FRAME, "label": "This frame", "tip": "The picture at the playhead"},
                {"value": SHOT, "label": f'{label} · {n} frame{"s" * (n != 1)}', "tip": "The shot's frames, as numbered pictures"},
                {"value": VIDEO, "label": f"{label} · MP4 video", "tip": "The shot as an MP4 video, with a small -share.mp4 copy beside it"}]

    def action_text(self):
        if self._choice == FRAME:
            return "Render this frame"
        return f"Render {self._frames()} frames" + (" as MP4" if self._choice == VIDEO else "")

    def _frames(self) -> int:
        s = self._settings()
        return s["end"] - s["start"] + 1

    def replaceable(self):
        return self._choice != SHOT

    def _stem(self):
        return f'{self.bridge.doc.item_id or "doc"}_{self.bridge.shot_id}'

    def file_name(self):
        if self._choice == VIDEO:
            return f"{self._stem()}.mp4"
        ext = self._settings()["formats"][0]
        return f"{self._stem()}_f{self.bridge.frame:04d}.{ext}" if self._choice == FRAME else f"{self._stem()}.{{frame}}.{ext}"

    def default_folder(self):
        doc = self.bridge.doc
        if not (doc.folder and doc.item_id):
            return "The render cache"
        kept = self._kept()[1] if not self.running() else None      # Render continues a kept render: its own version
        return str(kept.with_name(kept.name[:-len(".partial")])) if kept is not None else str(project.next_render(doc.folder, doc.item_id))

    def planned(self):
        if not self._folder:
            return None
        return Path(self._folder) / (self._stem() if self._choice == SHOT else self.file_name())   # a sequence: its own folder

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
        """The Passes row: only while the shot saves an EXR (absent for PNG and MP4, never greyed); Beauty is always in it."""
        if self._choice == VIDEO or "exr" not in self._settings()["formats"] or self._settings()["renderer"] != "cycles":
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

    @Property(str, notify=own)
    def resumeLine(self):
        """"Continues from 130 finished frames": a stopped or failed render of exactly this shot render left frames that
        Render will reuse (rostrum3d.mcp.resume); "" otherwise, and while one runs. Cheap when nothing was kept."""
        return "" if self.running() else resume.continues_text(self._kept()[0])

    def _kept(self) -> tuple[int, Path | None]:
        """(finished frames, the kept folder) a stopped render of exactly what Render makes now left; (0, None) if none."""
        b = self.bridge
        if self._choice == FRAME or not resume.kept_folders(b.doc.folder, b.doc.item_id, self._stem()):
            return 0, None
        try:
            scene, info, s, _ = self.plan_now()
        except ValueError:
            return 0, None
        info = {**info, "start": s["start"], "end": s["end"]}
        cyc = engine_fields(s)
        if self._choice == VIDEO:
            size = (s["width"] - s["width"] % 2, s["height"] - s["height"] % 2)
            key = video_key(scene, info, s["start"], s["end"], s["renderer"], size, cyc, 0, False, None)
            n = video_kept(b.doc.folder, b.doc, info, key, s["start"], s["end"], False)
        else:
            key = sequence_key(scene, info, (s["width"], s["height"]), s["formats"], cyc, s["passes"], s["renderer"])
            n = kept_count(b.doc.folder, b.doc, info, key, s["formats"], self._stem())
        return n, resume.find(b.doc.folder, b.doc.item_id, self._stem(), key) if n else None

    def _finish(self, result, error):
        """A stop that kept frames says so, and how to go on (the kit's "Cancelled" otherwise)."""
        kept = getattr(self, "_done_frames", 0) if self._stopping else 0
        super()._finish(result, error)
        if self._state == "cancelled" and kept:
            self._note = f"Stopped · {kept} finished frame{'s' * (kept != 1)} kept: Render again continues from them"
            self.bridge._set_status(self._note)
            self.changed.emit()

    # ---- the job ----------------------------------------------------------------------------------------------
    def begin(self, out, overwrite):
        b = self.bridge
        if b.render.running() or b.queue.running():
            raise RuntimeError("a render is already running; wait for it or cancel it first")
        if self._choice == VIDEO:
            check_ffmpeg("render")
        scene, info, s, _ = self.plan_now()             # the shot's render settings: what the estimate measured
        info = {**info, "start": s["start"], "end": s["end"]}
        size = (s["width"] - s["width"] % 2, s["height"] - s["height"] % 2) if self._choice == VIDEO else (s["width"], s["height"])
        return {"info": info, "video": self._choice == VIDEO, "renderer": s["renderer"], "cycles": engine_fields(s), "scene": scene, "doc": DocView.of(b.doc),
                "frame": b.frame, "folder": b.doc.folder, "out": out, "size": size,
                "shot": self._choice != FRAME, "formats": s["formats"], "passes": s["passes"], "stem": self._stem(),
                "main": s["formats"][0]}

    def work(self, plan, progress):
        self._halt = halt = threading.Event()
        engine = self._engine = self._make_engine()
        try:
            if halt.is_set():
                raise RuntimeError("Export cancelled")
            self._done_frames = 0
            run = self._video if plan["video"] else self._sequence if plan["shot"] else self._frame
            done, files = run(plan, engine, self._counting(plan, progress) if plan["shot"] else progress, halt.is_set)
            if plan["out"] is not None:
                files = self._copy(plan, files)
            first = files[0]
            file = first.with_name(f"{first.name.rsplit('.', 2)[0]}.{{frame}}{first.suffix}") if plan["shot"] and not plan["video"] else first
            return {"files": [str(f) for f in files], "file": str(file), "version": done.name}
        finally:
            self._engine = None
            engine.close()

    @staticmethod
    def _frame(plan, engine, progress, stopped):
        done, files, _ = still("export", plan["doc"], plan["info"], plan["scene"], engine, plan["frame"], plan["renderer"],
                               plan["size"], plan["formats"], 0, plan["cycles"], plan["folder"], plan["passes"], stopped)
        return done, files

    def _counting(self, plan, progress):
        """The worker's progress for a shot: the bar, and "Frame 12 of 120 · about 4 min left", the frame being drawn (with
        "continues from 130 finished frames" when it does). The time left is this render's own rate, from the first frame it
        drew here on: no number until one frame is done (render_guess: never a confident wrong number)."""
        total, kept, since = plan["info"]["end"] - plan["info"]["start"] + 1, [0], []

        def frames(i, n=total):
            self._done_frames = i
            progress(i / max(n, 1))
            now = time.perf_counter()
            if not since or i < since[0][0]:
                since[:] = [(i, now)]
            cont = resume.continues_text(kept[0])
            if i < n:
                i0, t0 = since[0]
                left = f" · {words_left((now - t0) / (i - i0) * (n - i))}" if i > i0 else ""
                self.phase(f"Frame {i + 1} of {n}{left}" + (f" · {cont[0].lower()}{cont[1:]}" if cont else ""))
            elif plan["shot"] and not plan["video"]:
                self.phase("")

        def resumed(n):
            kept[0] = n
            frames(n)
        frames.resumed = resumed
        return frames

    @staticmethod
    def _sequence(plan, engine, progress, stopped):
        return sequence("export", plan["doc"], plan["info"], plan["scene"], engine, plan["size"], plan["formats"],
                        plan["cycles"], plan["folder"], plan["stem"], progress, plan["passes"], stopped,
                        renderer=plan["renderer"], resumed=progress.resumed)

    def _video(self, plan, engine, progress, stopped):
        info = plan["info"]
        done, files, _ = video("export", plan["doc"], info, plan["scene"], engine, plan["size"], plan["renderer"], plan["cycles"],
                               info["start"], info["end"], plan["folder"], progress=progress, stopped=stopped,
                               resumed=progress.resumed, say=self.phase)
        return done, files

    @staticmethod
    def _copy(plan, files):
        """Browse: the same files, copied there (a picture under the chosen name; a sequence into its own new folder)."""
        out = plan["out"]
        if plan["video"]:                                 # the mp4 under the chosen name, its share copy beside it
            out.parent.mkdir(parents=True, exist_ok=True)
            pairs = [(files[0], out), (files[1], out.with_name(out.stem + "-share.mp4"))]
            for src, dst in pairs:
                shutil.copyfile(src, dst)
            return [dst for _, dst in pairs]
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
