"""The Render page's queue (SPEC §11.3): the shots' renders as jobs of the project's ONE jobs queue (rostrum_core.mcp.jobs,
InProcessJobs, the stand-in for the project service's queue), run one at a time, the rest waiting in order.

Operations (screen state, never the document; rule 4): `render.queue.add {shot}`, `render.queue.move {job, index}`,
`render.queue.cancel {job}`, all through `call`: the page's buttons, the Ctrl K commands and scripted steps use it.
A job reads a snapshot taken when it was added (scene, shot, settings: the shot's own render fields, the sheet's Save
as), renders its frames through rostrum3d.mcp.sequence (the same path as the sheet's Export of the shot) on its own
engine process, into the project's next render version via `.partial`. Cancel ends that process by its own handle
(the job's stop hook; never by name); the row then says "Render cancelled". The frames it finished stay in its `.partial`
folder, and the same render queued again continues from them (rostrum3d.mcp.resume); one cancelled before its first frame leaves nothing.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp.jobs import InProcessJobs
from rostrum_core.mcp.reply import Reply
from rostrum3d.compile import describe, shot_info
from rostrum3d.engine import Engine
from rostrum3d.mcp.render import DocView
from rostrum3d.mcp.sequence import sequence
from rostrum3d.render_fields import engine_fields, passes, settings

from . import queue_rows
from .queue_view import QueueView
from .export3d import FORMATS

OPS = ("render.queue.add", "render.queue.move", "render.queue.cancel")


class RenderQueue(QObject):
    changed = Signal()

    def __init__(self, bridge, engine_factory=None, jobs=None, parent=None):
        super().__init__(parent or bridge)
        self._b, self._make_engine = bridge, engine_factory or Engine
        self.jobs = jobs or InProcessJobs(workers=1)       # one heavy job at a time on this laptop
        self._meta: dict[str, dict] = {}
        self._ticked: set[str] = set()
        self._rows: list[dict] = []
        self.view = QueueView(self)
        self._poll = QTimer(self, interval=250, timeout=self.refresh)
        bridge.outlineChanged.connect(self.changed)        # shots renamed, added, removed

    # ---- what QML reads ------------------------------------------------------------------------------------
    @Property("QVariantList", notify=changed)
    def rows(self):
        return self._rows

    @Property("QVariantList", notify=changed)
    def shots(self):
        b, infos = self._b, {}
        for s in b.shots:
            try:
                infos[s["value"]] = shot_info(b.doc.data, s["value"])
            except ValueError:
                pass                                         # a shot without a camera can't be listed with a length
        last = queue_rows.last_renders(b.doc.folder, b.doc.item_id)
        return queue_rows.shot_rows(b.shots, infos, b.shot_id, self._ticked, last)

    @Property(int, notify=changed)
    def tickedCount(self):
        return len([s for s in self._b.shots if s["value"] in self._ticked])

    @Property(QObject, constant=True)
    def shown(self):
        return self.view

    def running(self) -> bool:
        """One of this page's renders is on the graphics card (the sheet and the Render button wait for it)."""
        return any(j.status == "running" for j in self.jobs.listing() if j.id in self._meta)

    # ---- the operations ------------------------------------------------------------------------------------
    def call(self, op: str, args: dict):
        """The one door for render.queue.* (buttons, Ctrl K, steps). Returns the job id."""
        if op == "render.queue.add":
            job = self._add(args["shot"], bool(args.get("exr")))
            if args.get("first"):
                self.jobs.move(job.id, 0)
        elif op == "render.queue.move":
            job = self.jobs.move(args["job"], args["index"])
        elif op == "render.queue.cancel":
            job = self.jobs.cancel(args["job"])
        else:
            raise RostrumError(codes.BAD_ARGUMENT, "render queue", op, f"is not one of {', '.join(OPS)}")
        self.refresh()
        return job.id

    def _call(self, op, args) -> str:
        out = []
        self._b._guard(lambda: out.append(self.call(op, args)))
        return out[0] if out else ""

    @Slot(str, result=str)
    def add(self, shot_id):
        return self._call("render.queue.add", {"shot": shot_id})

    @Slot(str, result=str)
    def renderNext(self, shot_id):
        """The page's Render (F12): this shot next (it starts at once when nothing else is running)."""
        return self._call("render.queue.add", {"shot": shot_id, "first": True})

    @Slot(str, result=str)
    def renderNow(self, shot_id):
        """A render for a Send to 2D (send_qt.py): next in line, always with EXR frames (what 2D reads)."""
        return self._call("render.queue.add", {"shot": shot_id, "first": True, "exr": True})

    @Slot()
    def addTicked(self):
        for s in self._b.shots:
            if s["value"] in self._ticked:
                self.add(s["value"])

    @Slot(str, int)
    def move(self, job_id, index):
        self._call("render.queue.move", {"job": job_id, "index": index})

    @Slot(str)
    def cancel(self, job_id):
        self._call("render.queue.cancel", {"job": job_id})

    @Slot(str)
    def toggleTick(self, shot_id):
        self._ticked ^= {shot_id}
        self.changed.emit()

    def commands(self) -> list[dict]:
        """Ctrl K: add each shot to the queue; cancel each render still waiting or running (the same `call`)."""
        return queue_rows.commands(self._b.shots, self._rows, lambda op, args: self._call(op, args))

    @Slot(str)
    def openFolder(self, path):
        """A render's folder in the system's file browser (a person's click only)."""
        if path and Path(path).is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            self._b.fail_line(f"Error: open folder: {path or 'this shot has no render yet'} is not there.")

    @Slot(str)
    def show(self, job_id):
        row = next((r for r in self._rows if r["id"] == job_id and r["status"] == "done"), None)
        self.view.put(row or {})

    # ---- the job -----------------------------------------------------------------------------------------------
    def _add(self, shot_id, exr=False):
        b = self._b
        shot = next((x for x in b.doc.data["shots"] if x["id"] == shot_id), None)
        if shot is None:
            raise RostrumError.not_found("render queue", "shot", shot_id, {s["id"]: s for s in b.doc.data["shots"]}, "the shots")
        info = shot_info(b.doc.data, shot_id)
        s = settings(shot, info)
        plan = {"doc": DocView.of(b.doc), "scene": describe(b.doc.data, shot_id, b.doc.folder), "info": {**info, "start": s["start"], "end": s["end"]},
                "size": (s["width"], s["height"]), "renderer": s["renderer"], "cycles": engine_fields(s),
                "formats": sorted(set(FORMATS[b.exporter.format]) | ({"exr"} if exr else set())), "folder": b.doc.folder,
                "shot": shot}                           # its Passes go into an EXR (render_fields.passes)
        label = next((x["label"] for x in b.shots if x["value"] == shot_id), shot_id)
        meta = {"label": label, "quality": s["quality"].capitalize(), "size": f'{s["width"]} × {s["height"]}',
                "frames": s["end"] - s["start"] + 1, "pid": None}
        job = self.jobs.submit(f"render {shot_id}", lambda job: self._work(job, plan, meta))
        self._meta[job.id] = meta
        self._poll.start()
        return job

    def _work(self, job, plan, meta) -> Reply:
        while self._b.render.running() or self._b.exporter.running():     # the card is this window's other render's
            job.progress(0, meta["frames"], "waiting for the other render to finish")
            time.sleep(0.25)
        engine = self._make_engine()
        job.on_cancel(lambda: _end(engine, meta))

        def frames(i, n):
            meta["pid"] = engine.pid                         # the engine process this job runs on (cancel ends it)
            job.progress(i, n, "")

        try:
            job.progress(0, meta["frames"], "starting")
            done, files = sequence("render queue", plan["doc"], plan["info"], plan["scene"], engine, plan["size"], plan["formats"],
                                   plan["cycles"], plan["folder"], progress=frames,
                                   passes=passes(plan["shot"]) if "exr" in plan["formats"] and plan["renderer"] == "cycles" else None,
                                   stopped=job.cancel_requested.is_set, renderer=plan["renderer"])
        finally:
            engine.close()
        pngs = [f for f in files if f.suffix == ".png"]
        meta.update(folder=str(done), picture=str(pngs[-1]) if pngs else "")
        return Reply(f"Rendered {meta['label']}: {len(files)} files in {done}", {"folder": str(done)}, files)

    @Slot()
    def refresh(self):
        rows = queue_rows.queue_rows(self.jobs.listing(), self._meta)
        if rows != self._rows:
            ended = {r["id"] for r in rows if r["status"] in ("done", "failed", "cancelled")} - {
                r["id"] for r in self._rows if r["status"] in ("done", "failed", "cancelled")}
            self._rows = rows
            for r in rows:
                if r["id"] in ended:
                    if r["status"] == "failed":
                        self._b.fail_line(f'Error: render {r["shot"]}: {r["reason"]}')
                    else:
                        self._b.say(f'{r["shot"]}: {r["word"]} · {r["reason"] or r["took"]}')
            if ended and (sim := getattr(self._b, "_sim", None)) is not None:
                sim.adopt()                         # a simulation a render computed becomes the shot's stored one
            self.changed.emit()
        if not any(r["status"] in ("queued", "running") for r in rows):
            self._poll.stop()

    def close(self):
        for j in self.jobs.listing():
            if j.id in self._meta and j.status in ("queued", "running"):
                self.jobs.cancel(j.id)


def _end(engine, meta):
    """The job's stop hook: end its own engine process by its Popen handle (never by name), for good."""
    meta["ended_pid"], meta["ended_proc"] = engine.pid, engine.proc
    engine.kill(for_good=True)
