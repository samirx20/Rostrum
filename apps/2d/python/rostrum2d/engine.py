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

import json
import mmap
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import settings

LOG_DIR = settings.logs_dir()
RETRY = {"frame", "bones", "outline", "measure", "scene", "place"}     # short requests that are safe to send again
QUICK_S = 30.0                                                  # dying again this soon after a restart: give up
# Short, so the top bar's status line shows them whole; the log line says the rest (exit code, the old log).
RESTARTED = "The drawing engine restarted. Nothing was lost."
GAVE_UP = "Drawing stopped twice. Save, then reopen."


class EngineError(RuntimeError):
    plain = False                                    # True: the message is a whole sentence for the person, as it is


class _Died(EngineError):
    pass


def _gave_up() -> EngineError:
    e = EngineError(GAVE_UP)
    e.plain = True
    return e


def _log_line(text: str):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}", file=sys.stderr, flush=True)


def find_exe() -> Path:
    """The engine program, in settings.py's one order: ROSTRUM2D_ENGINE, else the release build, then the agents' `agent`
    build (the installed app carries the latter at the same place)."""
    exe = settings.engine_exe()
    if exe is None:
        raise EngineError(f"2D engine not found: none of {', '.join(map(str, settings.engine_candidates()))}; "
                          "build apps/2d/engine (in an install: reinstall Rostrum2D) or set ROSTRUM2D_ENGINE")
    return exe


class Engine:
    def __init__(self, exe: Path | None = None):
        self.exe = exe or find_exe()
        if not self.exe.exists():
            raise EngineError(f"2D engine not found: {self.exe} (set ROSTRUM2D_ENGINE)")
        self.scene, self._shm = None, None           # _shm: (name, mmap) of the engine's frame memory (pixels)
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

    def _request(self, req: dict, timeout_s: float = 60.0, progress=None) -> dict:
        if self.proc.poll() is not None:             # it died between requests
            self._restart()
        try:
            return self._send(req, timeout_s, progress)
        except _Died:
            if next(iter(req)) not in RETRY:
                raise
            self._restart()
            return self._send(req, timeout_s, progress)

    def _send(self, req: dict, timeout_s: float, progress) -> dict:
        t0 = time.perf_counter()
        try:
            self.proc.stdin.write((json.dumps(req) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
            while True:
                try:
                    line = self._lines.get(timeout=max(0.0, t0 + timeout_s - time.perf_counter()))
                except queue.Empty:
                    self.proc.kill()                     # stuck: ended, so the next request starts a fresh one
                    _log_line(f"the 2D drawing engine (pid {self.pid}) gave no answer to {next(iter(req))} in "
                              f"{timeout_s:.0f} s and was ended; its log: {self.log_path}")
                    raise _Died(f"2D engine (pid {self.pid}) gave no answer to {next(iter(req))} in {timeout_s:.0f} s; "
                                f"log {self.log_path}") from None
                if line is None:
                    raise _Died(f"2D engine (pid {self.pid}) ended without a reply; log {self.log_path}")
                out = json.loads(line)
                if set(out) != {"progress", "of"}:           # export's per-frame progress lines (keys in any order)
                    break
                if progress:
                    progress(out["progress"], out["of"])
        except OSError as e:
            raise _Died(f"2D engine (pid {self.pid}) stopped: {e}; log {self.log_path}") from e
        if "error" in out:
            raise EngineError(f"2D engine refused {next(iter(req))}: {out['error']}")
        out["ms"] = (time.perf_counter() - t0) * 1000
        return out

    def load(self, scene: dict):
        """Load or replace the scene; the engine checks it whole, so a bad scene fails here, loudly. With no working
        graphics driver the engine draws the same frames on the processor and `fallback` says so."""
        self.fallback = self._request({"scene": scene}).get("fallback")
        self.scene = scene

    def _props(self) -> dict:
        if self.scene is None:
            raise EngineError("no scene loaded (Engine.load)")
        return self.scene["comp"]["props"]

    def still(self, t: float, png: Path) -> dict:
        self._props()
        png = Path(png)
        png.parent.mkdir(parents=True, exist_ok=True)
        out = self._request({"frame": {"t": t, "image": str(png)}})
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

    def place(self, t: float, ids: list[str]) -> dict[str, dict]:
        """Where each layer is drawn at `t` (ENGINE_CONTRACT.md § 1 `place`), from the page the frame lays out, through its
        groups, the camera and tilt: {id: {"m": 3×3 own px -> comp px (projective, row-major), "w", "h": its own box,
        "edge": its true outline in comp px as path data}}. placement.py turns points through it; an undrawn layer fails."""
        self._props()
        return self._request({"place": {"t": t, "ids": list(ids)}})["layers"]

    def measure(self, items: list[dict]) -> dict[str, tuple[float, float]]:
        """Each text's laid-out box (w, h) in its own px, by the code that draws it: items are {id, and the text's
        evaluated fields} (ENGINE_CONTRACT.md § 1 `measure`). One round trip for the list; needs no scene loaded.
        Callers go through textsize.py, which keeps what was measured."""
        sizes = self._request({"measure": {"items": items}})["sizes"]
        return {k: (float(w), float(h)) for k, (w, h) in sizes.items()}

    def pixels(self, t: float, samples: int | None = None, scale: float = 1.0, view: dict | None = None,
               place: list[str] | None = None) -> tuple[memoryview, int, int, int]:
        """The frame at `t` as straight-alpha RGBA8 in the engine's shared memory (no PNG, no pipe; Windows):
        (view, width, height, stride). The view is valid until the frame after next is asked for; copy it.
        `samples`: motion-blur steps for this frame instead of the composition's (1 = no blur: fast playback).
        `scale`: 1, 0.5 or 0.25 × the composition's size, the same picture drawn smaller (playing); width and
        height are then the smaller size. `view` {x, y, w, h, scale}: only that part of the composition (comp px),
        drawn at any scale (the zoomed-in canvas, sharp). `place`: layer ids whose `place` (see place) comes with this
        frame, kept in `self.placed` ({} without)."""
        self._props()
        req = {"t": t, "pixels": True, **({"shutterSamples": samples} if samples else {}), **({"scale": scale} if scale != 1 else {}),
               **({"view": view} if view else {}), **({"place": place} if place else {})}
        out = self._request({"frame": req})
        self.placed, shm, self.timing = out.get("place") or {}, out["shm"], out.get("timing") or {}
        if shm["format"] != "rgba8":
            raise EngineError(f"pixels: the engine sent {shm['format']}; the canvas reads rgba8")
        if self._shm is None or self._shm[0] != shm["name"]:   # a new block when the frame size changes
            if self._shm is not None:
                self._shm[1].close()
            self._shm = (shm["name"], mmap.mmap(-1, shm["size"], tagname=shm["name"], access=mmap.ACCESS_READ))
        view = memoryview(self._shm[1])[shm["offset"]:shm["offset"] + shm["bytes"]]
        return view, shm["width"], shm["height"], shm["stride"]

    def video(self, mp4: Path, start: float = 0.0, end: float | None = None, progress=None, quality: str | None = None,
              bitrate: float | None = None) -> dict:
        """An MP4 through the formats table's encoder (io/formats.py: the OS's own H.264); `quality` or `bitrate` (Mbit/s)."""
        from .io import formats                      # the table imports find_exe from here
        p = self._props()
        fps, end, w, h = p["fps"], p["duration"] if end is None else end, p["width"], p["height"]
        mp4, f = Path(mp4), formats.get("mp4")
        mp4.parent.mkdir(parents=True, exist_ok=True)
        encode = f.build(str(mp4), w, h, fps, 8, 0, formats.kbps(f, w, h, fps, quality, bitrate))
        out = self._request({"export": {"start": start, "end": end, "file": str(mp4), "progress": progress is not None,
                                        "encode": encode}},
                            timeout_s=3600.0, progress=progress)
        if not mp4.is_file() or mp4.stat().st_size == 0:
            raise EngineError(f"export wrote no video: {mp4}; log {self.log_path}")
        return {"file": str(mp4), "frames": out["frames"], "fps": fps, "timing": out["timing"]}

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
