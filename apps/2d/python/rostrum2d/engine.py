"""The handle on Rostrum2D's engine: one long-lived `serve` process (ENGINE_CONTRACT.md). The GUI canvas, the
look tools and exports all render through it, the same way (preview ≡ export).

    with Engine() as eng:
        eng.load(scene)                 # scene.describe(doc.data, comp); load again after a change
        eng.still(1.2, png)             # one frame at 1.2 s
        eng.video(mp4)                  # the whole comp (or start=, end=)
        eng.measure([{"id": "t", **text_fields}])   # {"t": (w, h)}: a text's laid-out box (textsize.py keeps them)

The engine holds the scene and evaluates every frame itself (keys, easing, drawing); Python only describes it.
"""
from __future__ import annotations

import json
import mmap
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]                         # apps/2d
LOG_DIR = Path.home() / ".rostrum" / "logs"


class EngineError(RuntimeError):
    pass


def find_exe() -> Path:
    """ROSTRUM2D_ENGINE, else this checkout's engine build (release, then the agents' `agent` profile)."""
    if os.environ.get("ROSTRUM2D_ENGINE"):
        return Path(os.environ["ROSTRUM2D_ENGINE"])
    for profile in ("release", "agent"):
        for p in (HERE / "engine" / "target" / profile).glob("rostrum*.exe"):
            return p
    raise EngineError(f"2D engine not built: no rostrum*.exe in {HERE / 'engine' / 'target'} (release or agent); "
                      "build apps/2d/engine or set ROSTRUM2D_ENGINE")


def h264(out: Path, w: int, h: int, fps: int) -> dict:
    return {"program": "ffmpeg", "args": [
        "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
        "-r", str(fps), "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264",
        "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "bt709", str(out)]}


class Engine:
    def __init__(self, exe: Path | None = None):
        exe = exe or find_exe()
        if not exe.exists():
            raise EngineError(f"2D engine not found: {exe} (set ROSTRUM2D_ENGINE)")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log_path = LOG_DIR / f"engine2d-{os.getpid()}-{int(time.time())}.log"
        self._log = open(self.log_path, "wb")
        self.proc = subprocess.Popen([str(exe), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self._log)
        self.pid, self.scene = self.proc.pid, None
        self._shm = None                             # (name, mmap) of the engine's frame memory (pixels)

    def _request(self, req: dict, timeout_s: float = 60.0, progress=None) -> dict:
        t0 = time.perf_counter()
        try:
            self.proc.stdin.write((json.dumps(req) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
            while True:
                line = self.proc.stdout.readline()
                if not line:
                    raise EngineError(f"2D engine (pid {self.pid}) ended without a reply; log {self.log_path}")
                out = json.loads(line)
                if set(out) != {"progress", "of"}:           # export's per-frame progress lines (keys in any order)
                    break
                if progress:
                    progress(out["progress"], out["of"])
        except OSError as e:
            raise EngineError(f"2D engine (pid {self.pid}) stopped: {e}; log {self.log_path}") from e
        if time.perf_counter() - t0 > timeout_s:
            raise EngineError(f"2D engine took over {timeout_s} s for {next(iter(req))}")
        if "error" in out:
            raise EngineError(f"2D engine refused {next(iter(req))}: {out['error']}")
        out["ms"] = (time.perf_counter() - t0) * 1000
        return out

    def load(self, scene: dict):
        """Load or replace the scene; the engine checks it whole, so a bad scene fails here, loudly."""
        self._request({"scene": scene})
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

    def measure(self, items: list[dict]) -> dict[str, tuple[float, float]]:
        """Each text's laid-out box (w, h) in its own px, by the code that draws it: items are {id, and the text's
        evaluated fields} (ENGINE_CONTRACT.md § 1 `measure`). One round trip for the list; needs no scene loaded.
        Callers go through textsize.py, which keeps what was measured."""
        sizes = self._request({"measure": {"items": items}})["sizes"]
        return {k: (float(w), float(h)) for k, (w, h) in sizes.items()}

    def pixels(self, t: float) -> tuple[memoryview, int, int, int]:
        """The frame at `t` as straight-alpha RGBA8 in the engine's shared memory (no PNG, no pipe; Windows):
        (view, width, height, stride). The view is valid until the frame after next is asked for; copy it."""
        self._props()
        shm = self._request({"frame": {"t": t, "pixels": True}})["shm"]
        if shm["format"] != "rgba8":
            raise EngineError(f"pixels: the engine sent {shm['format']}; the canvas reads rgba8")
        if self._shm is None or self._shm[0] != shm["name"]:   # a new block when the frame size changes
            if self._shm is not None:
                self._shm[1].close()
            self._shm = (shm["name"], mmap.mmap(-1, shm["size"], tagname=shm["name"], access=mmap.ACCESS_READ))
        view = memoryview(self._shm[1])[shm["offset"]:shm["offset"] + shm["bytes"]]
        return view, shm["width"], shm["height"], shm["stride"]

    def video(self, mp4: Path, start: float = 0.0, end: float | None = None, progress=None) -> dict:
        p = self._props()
        fps, end = p["fps"], p["duration"] if end is None else end
        mp4 = Path(mp4)
        mp4.parent.mkdir(parents=True, exist_ok=True)
        out = self._request({"export": {"start": start, "end": end, "file": str(mp4), "progress": progress is not None,
                                        "encode": h264(mp4, p["width"], p["height"], fps)}},
                            timeout_s=3600.0, progress=progress)
        if not mp4.is_file() or mp4.stat().st_size == 0:
            raise EngineError(f"export wrote no video: {mp4}; log {self.log_path}")
        return {"file": str(mp4), "frames": out["frames"], "fps": fps, "timing": out["timing"]}

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
