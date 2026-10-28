"""The handle on Rostrum2D's engine: one long-lived `serve` process (ENGINE_CONTRACT.md). The GUI canvas, the
look tools and exports all render through it, the same way (preview ≡ export).

    with Engine() as eng:
        eng.load(scene)                 # scene.describe(doc.data, comp); load again after a change
        eng.still(1.2, png)             # one frame at 1.2 s
        eng.video(mp4)                  # the whole comp (or start=, end=)
        eng.measure([{"id": "t", **text_fields}])   # {"t": (w, h)}: a text's laid-out box (textsize.py keeps them)

The engine holds the scene and evaluates every frame itself (keys, easing, drawing); Python only describes it.

If the process dies (a crash, ended in Task Manager), the next request starts a new one and loads the scene again;
a short request that was cut off (a frame, a measure) is sent again. An engine that doesn't answer within the
request's time limit is ended and counts as dead: no wait on it can hang (a stuck graphics driver once kept the
window from ever showing). One line goes to the log (stderr) and `notice`
holds a sentence for the person. Dying again within QUICK_S of a restart is not retried: every request then fails
with one plain sentence (GAVE_UP). An export is never sent again (Cancel ends the engine on purpose).
"""
from __future__ import annotations

import inspect
import json
import mmap
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

from rostrum_core import bug

from . import scene_change, settings

LOG_DIR = settings.logs_dir()
RETRY = {"frame", "bones", "outline", "measure", "shapes", "scene", "change", "place"}   # short requests that are safe to send again
QUICK_S = 30.0                                                  # dying again this soon after a restart: give up
# The longest one frame may take, in a still or an export. Over it the engine counts as stuck: it is ended and the error names the frame; never a silent wait (p1, 2026-10-25).
FRAME_LIMIT_S = float(os.environ.get("ROSTRUM2D_FRAME_LIMIT_S") or 120.0)
# Short, so the top bar's status line shows them whole; the log line says the rest (exit code, the old log).
RESTARTED = "The drawing engine restarted. Nothing was lost."
GAVE_UP = "Drawing stopped twice. Save, then reopen."


class EngineError(RuntimeError):
    plain = False                                    # True: the message is a whole sentence for the person, as it is


class _Died(EngineError):
    pass


class Stuck(EngineError):
    """The engine drew nothing within FRAME_LIMIT_S and was ended. Not sent again: it would only get stuck again."""


def _gave_up() -> EngineError:
    e = EngineError(GAVE_UP)
    e.plain = True
    return e


def _log_line(text: str):
    bug.note(text)                      # never fails the request it reports on (a closed stderr pipe on Windows)


def find_exe() -> Path:
    """The engine program, in settings.py's one order: ROSTRUM2D_ENGINE, else the release build, then the agents' `agent`
    build (the installed app carries the latter at the same place)."""
    exe = settings.engine_exe()
    if exe is None:
        raise EngineError(f"2D engine not found: none of {', '.join(map(str, settings.engine_candidates()))}; "
                          "build apps/2d/engine (in an install: reinstall Rostrum2D) or set ROSTRUM2D_ENGINE")
    return exe


def _clock(s: float) -> str:
    s = round(s)
    return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def _progress(progress, line: dict):
    """An export's progress line to the caller: (done, total), plus the time so far and left in words to a job's
    progress (rostrum_core jobs: done, total, note) that takes a note."""
    if "leftS" not in line:
        return progress(line["progress"], line["of"])
    try:
        params = inspect.signature(progress).parameters
    except (TypeError, ValueError):
        params = {}
    if len(params) < 3 and not any(p.kind == p.VAR_POSITIONAL for p in params.values()):
        return progress(line["progress"], line["of"])
    left = "" if line["progress"] >= line["of"] else f", about {_clock(line['leftS'])} left"
    progress(line["progress"], line["of"], f"{_clock(line['elapsedS'])} so far{left}")


class Engine:
    def __init__(self, exe: Path | None = None):
        self.exe = exe or find_exe()
        if not self.exe.exists():
            raise EngineError(f"2D engine not found: {self.exe} (set ROSTRUM2D_ENGINE)")
        self.scene, self._shm = None, None           # _shm: (name, mmap) of the engine's frame memory (pixels)
        self.loaded: dict = {}                       # the last load: {"sent": "scene" | "change", "kept", "timing", "ms", "why" (sent whole)}
        self.placed: dict = {}                       # the last pixels frame's `place` reply
        self.timing: dict = {}                       # the last pixels frame's own split (its reply's `timing`)
        # Why it paints on the processor, in plain words (no working graphics driver; ROSTRUM2D_NO_GPU=1), or None on the GPU.
        self.fallback: str | None = None
        self.notice: str | None = None               # RESTARTED after a restart, until the screen has said it
        self._restarted_at = None
        self._stopped: EngineError | None = None     # set: never restarted again; every request raises it
        self._start()

    def _start(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log_path = LOG_DIR / f"engine2d-{os.getpid()}-{time.time_ns()}.log"
        self._log = open(self.log_path, "wb")
        self.proc = subprocess.Popen([str(self.exe), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self._log, creationflags=settings.NO_WINDOW)
        self.pid = self.proc.pid
        self._lines: queue.Queue = queue.Queue()     # the engine's reply lines, read by a thread; None: it ended
        threading.Thread(target=self._read, args=(self.proc.stdout, self._lines), daemon=True,
                         name=f"engine2d-{self.pid}").start()

    @staticmethod
    def _read(out, lines: queue.Queue):
        for line in iter(out.readline, b""):
            lines.put(line)
        lines.put(None)

    def _restart(self):
        """A new process for the dead one, the scene loaded again; GAVE_UP when it died again soon after the last restart."""
        if self._stopped:
            raise self._stopped
        code, old = self.proc.wait(), self.log_path
        if self._restarted_at is not None and time.monotonic() - self._restarted_at < QUICK_S:
            self._stopped = _gave_up()
            _log_line(f"the 2D drawing engine stopped again (exit code {code}) {time.monotonic() - self._restarted_at:.0f} s "
                      f"after a restart; not restarted again. Its log: {old}")
            raise self._stopped
        self._release()
        self._start()
        self._restarted_at = time.monotonic()
        _log_line(f"the 2D drawing engine stopped (exit code {code}) and was restarted (new pid {self.pid}); old log: {old}")
        if self.scene is not None:
            try:
                self._send({"scene": self.scene}, 60.0, None)
            except _Died:
                return self._restart()               # this soon: gives up, loudly
        self.notice = RESTARTED

    def _request(self, req: dict, timeout_s: float = 60.0, progress=None, stuck=None) -> dict:
        if self.proc.poll() is not None:             # it died between requests
            self._restart()
        try:
            return self._send(req, timeout_s, progress, stuck)
        except _Died:
            if next(iter(req)) not in RETRY:
                raise
            self._restart()
            return self._send(req, timeout_s, progress, stuck)

    def _send(self, req: dict, timeout_s: float, progress, stuck=None) -> dict:
        """`timeout_s`: the longest wait for the next line (each export progress line starts it again). `stuck(seen)`
        (`seen`: the last progress line or None): words naming what got stuck; with it a wait that runs out raises Stuck
        (never sent again), without it _Died (a short request is sent once more to a fresh engine)."""
        t0 = last = time.perf_counter()
        seen = None
        try:
            self.proc.stdin.write((json.dumps(req) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
            while True:
                try:
                    line = self._lines.get(timeout=max(0.0, last + timeout_s - time.perf_counter()))
                except queue.Empty:
                    self.proc.kill()                     # stuck: ended (an export's encoder ends with its pipe); the next request starts a fresh one
                    what = stuck(seen) if stuck else f"gave no answer to {next(iter(req))}"
                    _log_line(f"the 2D drawing engine (pid {self.pid}) {what} in {timeout_s:.0f} s and was ended; its log: {self.log_path}")
                    raise (Stuck if stuck else _Died)(f"2D engine (pid {self.pid}) {what} in {timeout_s:.0f} s and was stopped; "
                                                      f"log {self.log_path}") from None
                if line is None:
                    raise _Died(f"2D engine (pid {self.pid}) ended without a reply; log {self.log_path}")
                out = json.loads(line)
                if "progress" not in out or "ok" in out:     # export's per-frame progress lines
                    break
                seen, last = out, time.perf_counter()
                if progress:
                    _progress(progress, out)
        except OSError as e:
            raise _Died(f"2D engine (pid {self.pid}) stopped: {e}; log {self.log_path}") from e
        if "error" in out:
            raise EngineError(f"2D engine refused {next(iter(req))}: {out['error']}")
        out["ms"] = (time.perf_counter() - t0) * 1000
        return out

    def load(self, scene: dict):
        """Load or replace the scene; the engine checks it whole, so a bad scene fails here, loudly. When it holds a
        scene and the new one shares nodes with it (the same objects: scene_keep.py), only the change goes
        (scene_change.py), else the whole scene, with a log line saying why. `self.scene` is always the whole
        description now held; a restarted engine gets it whole. With no working graphics driver the engine draws
        the same frames on the processor and `fallback` says so. Why it went whole is a developer's fact, not a
        warning: kept in `loaded["why"]`, and logged only with ROSTRUM2D_LOG_SCENE=1 (stderr reaches agents)."""
        req, why = ({"scene": scene}, "the held scene was edited (a drag)") if self.edited else scene_change.request(self.scene, scene)
        if why and os.environ.get("ROSTRUM2D_LOG_SCENE") == "1":
            _log_line(f"2D scene sent whole: {why}")
        out = self._request(req)
        self.fallback = out.get("fallback")
        self.scene, self.edited = scene, False
        self.loaded = {"sent": next(iter(req)), "kept": out.get("kept", 0), "timing": out.get("timing") or {}, "ms": out["ms"],
                       "why": why or ""}

    edited = False          # `edit` changed the held scene: it no longer matches `self.scene`, the next load sends it whole

    def edit(self, edits: list[dict]) -> None:
        """Small changes to the held scene without resending it (ENGINE_CONTRACT.md `edit`: a drag's moves), all or
        nothing: [{"id", "props"?: {…}, "anim"?: {…}}]. The next `load` sends its scene whole."""
        self._props()
        self._request({"edit": edits})
        self.edited = True

    def _props(self) -> dict:
        if self.scene is None:
            raise EngineError("no scene loaded (Engine.load)")
        return self.scene["comp"]["props"]

    def still(self, t: float, png: Path) -> dict:
        self._props()
        png = Path(png)
        png.parent.mkdir(parents=True, exist_ok=True)
        fps = self._props()["fps"]
        out = self._request({"frame": {"t": t, "image": str(png)}}, FRAME_LIMIT_S,
                            stuck=lambda _: f"drew nothing for frame {round(t * fps)} ({t:.3f} s)")
        if not png.is_file():
            raise EngineError(f"2D engine said done but wrote no file: {png}")
        return out

    def bones(self, t: float) -> dict:
        """The posed rigs at `t`, in comp px: {rig id: {"bones": {id: {x, y, tipX, tipY, angle}}, "iks": {id: {targetX, targetY, gap}}}}."""
        self._props()
        return self._request({"bones": {"t": t}})["rigs"]

    def outline(self, id: str, t: float) -> str | None:
        """A path layer's varied (tapered / width-profile) stroke at `t` as filled-outline path data in its box's px
        (the engine's own geometry, what a frame draws); "" when none of the stroke shows, None for an even stroke."""
        self._props()
        return self._request({"outline": {"id": id, "t": t}})["d"]

    def place(self, t: float, ids: list[str], world: bool = False) -> dict[str, dict]:
        """Where each layer is drawn at `t` (ENGINE_CONTRACT.md § 1 `place`), from the page the frame lays out, through its
        groups, the frame and tilt: {id: {"m": 3×3 own px -> comp px (projective, row-major), "w", "h": its own box,
        "edge": its true outline in comp px as path data}}. placement.py turns points through it; an undrawn layer fails.
        `world`: where the canvas's world view draws it (world px, camera spec § 8.3) instead of the export."""
        self._props()
        req = {"t": t, "ids": list(ids), **({"world": {"x": 0, "y": 0, "w": 1, "h": 1}} if world else {})}
        return self._request({"place": req})["layers"]

    def measure(self, items: list[dict]) -> dict[str, tuple[float, float]]:
        """Each text's laid-out box (w, h) in its own px, by the code that draws it: items are {id, and the text's
        evaluated fields} (ENGINE_CONTRACT.md § 1 `measure`). One round trip for the list; needs no scene loaded.
        Callers go through textsize.py, which keeps what was measured."""
        sizes = self._request({"measure": {"items": items}})["sizes"]
        return {k: (float(w), float(h)) for k, (w, h) in sizes.items()}

    def layout(self, trees: list[dict]) -> list[dict[str, tuple[float, float, float, float]]]:
        """Each layout tree (a box with its children, texts and leaves: ENGINE_CONTRACT.md § 1 `layout`) laid out by
        the engine's CSS flex / grid with real text wrapping: per tree {node id: (x, y, w, h)}, the border box in its
        parent node's px. One round trip for the list; needs no scene loaded. Callers go through layout.py."""
        boxes = self._request({"layout": {"trees": trees}})["boxes"]
        return [{k: tuple(float(v) for v in b) for k, b in tree.items()} for tree in boxes]

    def shapes(self, items: list[dict]) -> dict[str, dict]:
        """Each parametric shape (arc, triangle, polygon, star, line, arrow, spiral) as the path it is drawn as: items
        are shape layers' fields with an id; {id: {path field: value}}, `d` in its own box px plus the path settings and
        (a line, a spiral) the stroke it draws with. One round trip; needs no scene loaded (ENGINE_CONTRACT.md § 1 `shapes`)."""
        return self._request({"shapes": {"items": items}})["paths"]

    def pixels(self, t: float, samples: int | None = None, scale: float = 1.0, view: dict | None = None,
               place: list[str] | None = None, world: dict | None = None, screen: bool = False,
               ahead: float | None = None) -> tuple[memoryview, int, int, int]:
        """The frame at `t` as straight-alpha RGBA8 in the engine's shared memory (no PNG, no pipe; Windows):
        (view, width, height, stride). The view is valid until the frame after next is asked for; copy it.
        `screen`: in the screen's form instead (BGRA, premultiplied: `self.format` "bgra8-premul", Qt's
        ARGB32_Premultiplied). `ahead`: the time asked for next (playing): the engine draws it while this one is shown.
        `samples`: motion-blur steps for this frame instead of the composition's (1 = no blur: fast playback).
        `scale`: above 0 and at most 1 × the composition's size, the same picture drawn smaller (playing: the size the
        canvas shows it at); width and height are then the smaller size (the whole composition as a `view`). `view` {x, y, w, h, scale}: only that part of the composition (comp px),
        drawn at any scale (the zoomed-in canvas, sharp). `place`: layer ids whose `place` (see place) comes with this
        frame, kept in `self.placed` ({} without). `world` {x, y, w, h, scale}: the world picture instead (camera spec
        § 8.4: any world px rectangle, the frame's quad holding the export; `place` then in world px); `self.quad` is
        the frame's corners in world px at t (None for other frames)."""
        p = self._props()
        if scale != 1:                               # any size: the whole composition as a view at that scale
            if view or world or not 0 < scale < 1:
                raise EngineError(f"pixels: scale {scale} is above 0 and below 1, and never with a view or the world")
            view = {"x": 0, "y": 0, "w": p["width"], "h": p["height"], "scale": scale}
        req = {"t": t, "pixels": True, **({"shutterSamples": samples} if samples else {}),
               **({"view": view} if view else {}), **({"place": place} if place else {}), **({"world": world} if world else {}),
               **({"screen": True} if screen else {}), **({"ahead": ahead} if ahead is not None else {})}
        out = self._request({"frame": req})
        self.placed, shm, self.timing = out.get("place") or {}, out["shm"], out.get("timing") or {}
        self.quad = out.get("quad")
        self.format = shm["format"]
        if self.format != ("bgra8-premul" if screen else "rgba8"):
            raise EngineError(f"pixels: the engine sent {self.format}; asked for {'bgra8-premul' if screen else 'rgba8'}")
        if self._shm is None or self._shm[0] != shm["name"]:   # a new block when the frame size changes
            if self._shm is not None:
                self._shm[1].close()
            self._shm = (shm["name"], mmap.mmap(-1, shm["size"], tagname=shm["name"], access=mmap.ACCESS_READ))
        view = memoryview(self._shm[1])[shm["offset"]:shm["offset"] + shm["bytes"]]
        return view, shm["width"], shm["height"], shm["stride"]

    def video(self, mp4: Path, start: float = 0.0, end: float | None = None, progress=None, quality: str | None = None,
              bitrate: float | None = None, timing_csv: Path | None = None) -> dict:
        """An MP4 through the formats table's encoder (io/formats.py: the OS's own H.264); `quality` or `bitrate` (Mbit/s)."""
        from .io import formats                      # the table imports find_exe from here
        from .io.export import encoded
        p = self._props()
        fps, end, w, h = p["fps"], p["duration"] if end is None else end, p["width"], p["height"]
        mp4, f = Path(mp4), formats.get("mp4")
        mp4.parent.mkdir(parents=True, exist_ok=True)
        encode = f.build(str(mp4), w, h, fps, 8, 0, formats.rate(f, w, h, fps, quality, bitrate))
        req = {"start": start, "end": end, "file": str(mp4), "encode": encode}
        if timing_csv is not None:
            req["timingCsv"] = str(timing_csv)
        out = self.export(req, progress)
        if not mp4.is_file() or mp4.stat().st_size == 0:
            raise EngineError(f"export wrote no video: {mp4}; log {self.log_path}")
        if out.get("warning"):
            _log_line(f"2D export: {out['warning']}")
        return {"file": str(mp4), "frames": out["frames"], "fps": fps, "timing": out["timing"], "adapter": out.get("adapter"),
                "gpu": out.get("gpu"), "warning": out.get("warning"), "workers": out.get("workers"),
                **(encoded(out["encoder"]) if out.get("encoder") else {})}

    def export(self, req: dict, progress=None) -> dict:
        """The engine's `export` request, watched: the engine sends a line per frame, and when none comes for
        FRAME_LIMIT_S it is ended and Stuck names where it stopped.
        No limit on the whole: a long film is fine while frames keep coming."""
        fps, start = self._props()["fps"], req.get("start", 0.0)

        def stuck(seen):
            done = seen["progress"] if seen else 0
            at = round(start * fps) + done
            if seen is None:
                return f"drew no frame of the export, not even its first (frame {at}, {start:.2f} s)"
            return f"drew nothing after {done} of {seen['of']} frames: stuck at frame {at} ({at / fps:.2f} s) or one just after"
        return self._request({"export": {**req, "progress": True}}, FRAME_LIMIT_S, progress, stuck)

    def kill(self):
        """End the process on purpose (Cancel): it is never restarted, and a request after this fails."""
        self._stopped = EngineError(f"2D engine (pid {self.pid}) was stopped on purpose (Cancel)")
        if self.proc.poll() is None:
            self.proc.kill()                         # our own child, by its handle

    def _release(self):
        if self._shm is not None:
            self._shm[1].close()
            self._shm = None
        self._log.close()

    def close(self):
        if self._shm is not None:
            self._shm[1].close()
            self._shm = None
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()                     # our own child, by its handle
                self.proc.wait()
        self._log.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
