"""The handle on Rostrum3D's engine: one long-lived `rostrum3d-core serve` process (ENGINE_CONTRACT.md § 1).
Look tools, renders and the GUI all go through it, the same way (preview ≡ export).

    eng = Engine()
    eng.ensure_scene(scene)                        # compile.describe(doc.data, shot); sent only when it changed
    eng.render(camera="cam", renderer="storm", frame=0, width=960, height=540, png="a.png")
    eng.pick(camera="cam", frame=0, width=960, height=540, x=480, y=270)

Every `ok: false` reply raises EngineError with the core's own message. A process that died is started again on
the next request, the scene is sent again, and the restart is reported in `take_notices()` (never silent).
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import queue
import subprocess
import threading
import weakref
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LOG_DIR = Path.home() / ".rostrum" / "logs"
from . import clay_faces
from .runtime import need_stylized, run_exe, runtime_env             # where the libraries are and how the engine program finds them


class EngineError(RuntimeError):
    pass


STYLIZED_VIEW = "Un-tone-mapped"     # the stylized look's colours are chosen, not measured light: shown as picked, no film curve


def _shown(req: dict) -> dict:
    """`req` with the stylized look's display view when it names none: the config's default (ACES 2.0) would dull and grey a
    flat Light-to-colour palette (a cream floor drawn grey). Another config (OCIO set) keeps its own default."""
    if req.get("renderer") != "stylized" or req.get("view") or os.environ.get("OCIO"):
        return req
    return {**req, "view": STYLIZED_VIEW}


_MINE: "weakref.WeakSet[Engine]" = weakref.WeakSet()    # every engine this program made


def own_pids() -> list[int]:
    """The engine processes this program started and still runs (the viewport's among them): on the graphics card they
    are ours, not "another job" (gpu_busy.busy's own_pids)."""
    return [e.proc.pid for e in list(_MINE) if e.proc is not None and e.proc.poll() is None]


@atexit.register
def _end_all():
    """This program is ending (a scripted run, a test, the window): no engine of ours outlives it, whatever thread was
    still waiting on one."""
    for e in list(_MINE):
        e.kill()


class Engine:
    def __init__(self, exe: Path | None = None, env: dict | None = None, args: tuple = ("serve",)):
        self.exe, self.args = (Path(exe) if exe else run_exe()), tuple(args)
        self._env = env
        self.proc, self.pid, self.log_path = None, None, None
        self._lines: queue.Queue = queue.Queue()
        self._hash, self._lock, self._notices = None, threading.RLock(), []
        self._held = None                               # the scene object last sent (ensure_scene: no hash for the same one)
        self._base = None                               # the scene last asked for, face shapes and all (clay_faces.py)
        self._shm = None                                # (name, mmap) of the engine's viewport memory (view)
        self.restarts = 0
        self.copies: dict = {}                          # the last scene's copies info: {id: {count, seen, camera}} (contract 2, copies)
        self._ours = None                               # the process we ended on purpose (run_stop, a cancelled render): its end is no crash
        self.stopped = False                            # kill(for_good=True): a cancelled job's engine never starts again
        _MINE.add(self)

    # --- the process
    def _start(self):
        if not self.exe.exists():
            raise EngineError(f"3D engine not found: {self.exe} (build apps/3d/core, or set ROSTRUM3D_CORE)")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log_path = LOG_DIR / f"engine3d-{os.getpid()}-{int(time.time() * 1000)}.log"
        with open(self.log_path, "wb") as log:
            self.proc = subprocess.Popen([str(self.exe), *self.args], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                         env=self._env or runtime_env())
        self.pid, self._hash, self._lines = self.proc.pid, None, queue.Queue()
        threading.Thread(target=self._read, args=(self.proc, self._lines), daemon=True).start()

    @staticmethod
    def _read(proc, lines: queue.Queue):
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)                                 # the process ended

    def _ensure_running(self):
        if self.stopped:
            raise EngineError(f"3D engine (pid {self.pid}) was stopped: its job was cancelled")
        if self.proc is None:
            self._start()
        elif self.proc.poll() is not None:
            code, old, ours = self.proc.returncode, self.log_path, self.proc is self._ours
            self.restarts += 1
            self._start()
            if not ours:                                # our own stop (run_stop) is no crash: nothing to report
                self._notices.append(f"The 3D engine had stopped (exit {code}, log {old}); it was started again (pid {self.pid}) "
                                     "and the scene sent again.")

    def take_notices(self) -> list[str]:
        out, self._notices = self._notices, []
        return out

    def _request(self, req: dict, timeout_s: float = 120.0, progress=None, step=None) -> dict:
        name = next(iter(req))
        with self._lock:
            self._ensure_running()
            t0 = time.perf_counter()
            try:
                self.proc.stdin.write((json.dumps(req) + "\n").encode("utf-8"))
                self.proc.stdin.flush()
            except OSError as e:
                raise EngineError(f"3D engine (pid {self.pid}) stopped before {name}: {e}; log {self.log_path}") from e
            while True:
                try:
                    line = self._lines.get(timeout=max(0.1, timeout_s - (time.perf_counter() - t0)))
                except queue.Empty:
                    self._ours = self.proc
                    self.proc.kill()                    # our own child, by its handle; the next request starts a new one
                    self.proc.wait()
                    raise EngineError(f"3D engine took over {timeout_s:g} s for {name}; it was stopped; log {self.log_path}") from None
                if line is None:
                    raise EngineError(f"3D engine (pid {self.pid}) ended without a reply to {name}; it is started again on the "
                                      f"next request; log {self.log_path}")
                out = json.loads(line)
                if "ok" in out:
                    break
                if ("progress" in out and progress) or ("step" in out and step):
                    try:
                        progress(out["progress"], out.get("of"), out) if "progress" in out else step(out)
                    except BaseException:               # a stop request: the render cannot be told to stop, so the process is
                        self._ours = self.proc
                        self.proc.kill()                # (our own child); the next request starts a new one
                        self.proc.wait()
                        raise
        if not out["ok"]:
            raise EngineError(f"3D engine refused {name}: {out.get('error', 'no reason given')}")
        out["ms"] = (time.perf_counter() - t0) * 1000
        return out

    # --- the requests
    def load(self, scene: dict) -> dict:
        scene = clay_faces.at(scene)                    # never the face shapes' frames themselves: the first frame's
        self._held = None                               # ensure_scene names it once the load is through
        out = self._request({"scene": scene})
        self.copies = out.get("copies") or {}
        self._hash = hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest()
        return out

    def ensure_scene(self, scene: dict, frame=None) -> bool:
        """Send the scene only when it differs from the one the engine holds. True when it was sent. A scene with
        painted clays whose surface isn't made yet (`paintLater`) is loaded twice: without their pictures, then with
        them (paint_scene.send). A scene whose clays change shape over the shot (face shapes) is sent as it is at
        `frame` (the shot's first when None); view and render send it again for the frames they draw."""
        self._base = scene
        return self._ensure(clay_faces.at(scene, frame))

    def _at(self, frame) -> None:
        """The held scene as it is at `frame`, when its clays change shape over the shot."""
        if self._base is not None and clay_faces.KEY in self._base:
            self._ensure(clay_faces.at(self._base, frame))

    def _ensure(self, scene: dict) -> bool:
        with self._lock:
            self._ensure_running()
            if self._hash and scene is self._held:      # the very scene sent last (draw.scene_of keeps one per document state)
                return False
            h = hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest()
            if h == self._hash:
                self._held = scene
                return False
            if scene.get("paintLater"):
                from . import paint_scene
                paint_scene.send(scene, self.load, self.texels_reply)
                self._hash = h                          # this scene, as asked, is what the engine holds
            else:
                self.load(scene)
            self._held = scene
            return True

    def render(self, progress=None, timeout_s: float | None = None, step=None, **req) -> dict:
        """One frame or `frames=[first, last]`; the files are checked here, so nothing is "done" without its file.
        `progress(i, of, line)` after each frame; `step(line)` while Cycles draws one ({"frame", "fraction", "ms"})."""
        if req.get("renderer") == "stylized":
            need_stylized("render")
        if self._base is None or clay_faces.KEY not in self._base:
            return self._render_one(progress, timeout_s, step, req)
        # face shapes: one request per run of frames with the same shapes, each after that run's scene; the replies'
        # frames in order, the progress counted over them all
        first, last = req["frames"] if req.get("frames") else (req["frame"], req["frame"])
        out, done = None, 0
        for a, b in clay_faces.runs(self._base, first, last):
            self._at(a)
            part = {k: v for k, v in req.items() if k not in ("frame", "frames")}
            part.update({"frames": [a, b]} if req.get("frames") else {"frame": a})
            on = progress and (lambda i, of, line, n0=done: progress(n0 + i, last - first + 1, line))
            got = self._render_one(on, timeout_s, step, part)
            done += b - a + 1
            if out is None:
                out = got
            else:
                out["frames"] += got.get("frames", [])
        return out

    def _render_one(self, progress, timeout_s, step, req) -> dict:
        req = _shown(req)
        out = self._request({"render": {**req, "progress": progress is not None or step is not None}},
                            timeout_s or float(req.get("timeoutS", 600)) + 60, progress, step)
        missing = [f[k] for f in out.get("frames", []) for k in ("exr", "png") if f.get(k) and not Path(f[k]).is_file()]
        if missing:
            raise EngineError(f"3D engine said done but wrote no file: {missing[0]}; log {self.log_path}")
        return out

    def simulate(self, progress=None, timeout_s: float = 900.0, **req) -> dict:
        """Rigid bodies (brief 25) and cloth (26b): `start`, `end`, `fps`, `folder` (where it writes bodies.bin and each
        cloth's cloth_<item>.bin), `ground`, `bodies`; the
        held scene must be the one without a stored result laid over it (sim/compute.py). `progress(i, of, line)` per
        frame. A refusal raises EngineError with the core's own words only (which thing, which frame, what to do)."""
        try:
            return self._request({"simulate": {**req, "progress": progress is not None}}, timeout_s, progress)
        except EngineError as e:
            said = "3D engine refused simulate: "
            if str(e).startswith(said):
                raise EngineError(str(e)[len(said):]) from None
            raise

    def pick(self, **req) -> dict:
        """`camera`, or a free camera `eye` + `target` + `fov` (§ 4)."""
        return self._request({"pick": req})

    def texels_reply(self, req: dict) -> dict:
        """The `texels` request (v1.22) as sent: camera fields as `pick`, frame, width, height and the `file` it writes
        (u, v, item, distance a pixel; texels.read reads it). texels.cached takes this as its `ask`."""
        return self._request({"texels": req})

    def texels(self, **req):
        """Which texel of which item each pixel of a camera's picture sees, as a texels.Picture (uv, item, items,
        distance, of(id)). Camera fields as `pick`; without a `file` a temporary one, read and removed."""
        from . import texels
        return texels.fetch(self.texels_reply, req)

    def geometry(self, item: str) -> dict:
        """The built mesh of a `mesh` or `combine` item in its own space: points, faceCounts, faceIndices."""
        return self._request({"geometry": {"item": item}})

    def copies_box(self, item: str, frame: int) -> dict:
        """What a copies item's copies take in the world at `frame`, as drawn: lo, hi ([x, y, z]; None with no copies)."""
        return self._request({"copies_box": {"item": item, "frame": frame}})

    def unfold(self, item: str, size: int = 2048) -> dict:
        """A `mesh` item's built mesh laid flat (xatlas): uvs (one u, v per face corner), charts, used."""
        return self._request({"unfold": {"item": item, "size": size}})

    def sculpt(self, **req) -> dict:
        """One live stroke event on a clay (CL1 contract § 4): `item`, `phase` begin | dab | end | cancel, the camera
        fields as `pick`, the pointer's new `points` in pixels and the brush. `end` (with the project `folder`) gives
        `dabs`, the stroke's file reference ("" when nothing landed) for clay.stroke."""
        return self._request({"sculpt": req})

    def clay_info(self, item: str) -> dict:
        """A clay as the core holds it: its shape's hash, steps applied, voxels, memoryMb, blocks."""
        return self._request({"clay_info": {"item": item}})

    def clay_pose(self, item: str, pose: list) -> dict:
        """A pose drag's live bone moves on a clay with bones (v1.18): `pose` holds one [12 numbers] move per bone, in
        its skin's order. The clay is drawn so until the next scene (or clay_pose). Gives `blocks` re-posed and `ms`."""
        return self._request({"clay_pose": {"item": item, "pose": pose}})

    def clay_grid(self, item: str, cells: int = 48, span: float = 0.0) -> dict:
        """The rest clay's inside sampled on a grid (v1.18), `cells` (8..128) along `span` (metres, the longest side
        round its pieces: clay_detail.span; 0: along its own bounds), on a lattice fixed in clay space: `origin` (the
        grid's low corner, clay space), `cell` (metres), `dims` [nx, ny, nz] and `inside` (base64, one byte per cell, 1
        inside, x fastest, then y, then z; cell centres at origin + (i + 0.5) × cell)."""
        return self._request({"clay_grid": {"item": item, "cells": cells, **({"span": span} if span > 0 else {})}})

    def view(self, **req) -> tuple[memoryview, int, int, int, dict]:
        """One live viewport picture (§ 4) as straight-alpha RGBA8 in the engine's shared memory (Windows):
        (view, width, height, stride, reply). The view is valid until the view after next is asked for; copy it."""
        if req.get("renderer") == "stylized":
            need_stylized("view")
        self._at(req.get("frame"))
        out = self._request({"view": _shown(req)})
        return (*self._pixels(out["shm"]), out)

    def sculpt_view(self, view: dict, **req) -> tuple[dict, tuple | None]:
        """A live stroke event and the viewport picture after it, in one request (CL2): (the sculpt reply, the
        picture as `view` gives it, or None when the engine drew none: an end or cancel)."""
        out = self._request({"sculpt": {**req, "view": view}})
        v = out.pop("view", None)
        return out, ((*self._pixels(v["shm"]), v) if v else None)

    def _pixels(self, shm: dict) -> tuple[memoryview, int, int, int]:
        import mmap
        if shm["format"] != "rgba8":
            raise EngineError(f"view: the engine sent {shm['format']}; the viewport reads rgba8")
        with self._lock:
            if self._shm is None or self._shm[0] != shm["name"]:   # a new block when the size or the process changes
                self._close_shm()
                self._shm = (shm["name"], mmap.mmap(-1, shm["size"], tagname=shm["name"], access=mmap.ACCESS_READ))
            view = memoryview(self._shm[1])[shm["offset"]:shm["offset"] + shm["bytes"]]
        return view, shm["width"], shm["height"], shm["stride"]

    def _close_shm(self):
        if self._shm is not None:
            self._shm[1].close()                        # BufferError if a caller still holds a view: release it first
            self._shm = None

    def inspect_usd(self, file: str | Path) -> dict:
        return self._request({"inspect_usd": {"file": str(file)}})

    def save(self, file: str | Path, flatten: bool = False) -> dict:
        return self._request({"save": {"file": str(file), "flatten": flatten}})

    def info(self) -> dict:
        return self._request({"info": {}})

    def release(self):
        """End the process on purpose (no restart notice): the next request starts a fresh one and sends the scene again.
        All its graphics memory goes back (the viewport leaving the Final look: ending one Hydra Cycles engine inside a
        running process is not safe, ending the process is)."""
        self.close()
        with self._lock:
            self.proc, self._hash = None, None

    def kill(self, for_good: bool = False):
        """End our own engine process now, by its handle (its PID), without waiting for the lock: safe from any thread,
        even while another thread is blocked on a reply (that request then fails loudly: the process ended).
        `for_good`: a cancelled job's engine: a later request fails instead of starting a new process."""
        self.stopped = self.stopped or for_good
        proc = self.proc
        if proc is not None and proc.poll() is None:
            self._ours = proc
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    def close(self):
        with self._lock:
            self._close_shm()
            if self.proc is not None and self.proc.poll() is None:
                try:
                    self.proc.stdin.close()
                    self.proc.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    self.proc.kill()                    # our own child, by its handle
                    self.proc.wait()
            self.proc = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
