"""The handle on Rostrum2D's engine: one long-lived `serve` process (ENGINE_CONTRACT.md). The GUI canvas, the
look tools and exports all render through it, the same way (preview ≡ export).

    with Engine() as eng:
        eng.load(scene)                 # scene.describe(doc.data, comp); load again after a change
        eng.still(1.2, png)             # one frame at 1.2 s
        eng.video(mp4)                  # the whole comp (or start=, end=)

Evaluation: the contract says the engine evaluates the scene per frame. Until the Rust side does (Team Hem),
`evaluator="python"` (the default) evaluates here (scene.frame_at) and sends page markup (stopgap_html, TEMPORARY).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from . import stopgap_html
from .scene import frame_at

HERE = Path(__file__).resolve().parents[2]                         # apps/2d
ARCHIVE_EXE = Path(r"C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT\native\target\release\rostrum-motion.exe")
LOG_DIR = Path.home() / ".rostrum" / "logs"


class EngineError(RuntimeError):
    pass


def find_exe() -> Path:
    """ROSTRUM2D_ENGINE, else this repo's engine build, else the archive's renderer."""
    if os.environ.get("ROSTRUM2D_ENGINE"):
        return Path(os.environ["ROSTRUM2D_ENGINE"])
    for p in (HERE / "engine" / "target" / "release").glob("rostrum*.exe"):
        return p
    return ARCHIVE_EXE


def h264(out: Path, w: int, h: int, fps: int) -> dict:
    return {"program": "ffmpeg", "args": [
        "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
        "-r", str(fps), "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264",
        "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "bt709", str(out)]}


class Engine:
    def __init__(self, exe: Path | None = None, evaluator: str = "python"):
        exe = exe or find_exe()
        if not exe.exists():
            raise EngineError(f"2D engine not found: {exe} (set ROSTRUM2D_ENGINE)")
        if evaluator != "python":
            raise EngineError("the engine's own scene evaluation isn't available yet; use evaluator='python'")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log_path = LOG_DIR / f"engine2d-{os.getpid()}-{int(time.time())}.log"
        self._log = open(self.log_path, "wb")
        self.proc = subprocess.Popen([str(exe), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self._log)
        self.pid, self.scene, self._opened = self.proc.pid, None, None
        self.caps = frozenset() if exe == ARCHIVE_EXE else frozenset({"gradient-text"})

    def _request(self, req: dict, timeout_s: float = 60.0) -> dict:
        t0 = time.perf_counter()
        try:
            self.proc.stdin.write((json.dumps(req) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
        except OSError as e:
            raise EngineError(f"2D engine (pid {self.pid}) stopped: {e}; log {self.log_path}") from e
        if not line:
            raise EngineError(f"2D engine (pid {self.pid}) ended without a reply; log {self.log_path}")
        if time.perf_counter() - t0 > timeout_s:
            raise EngineError(f"2D engine took over {timeout_s} s for {next(iter(req))}")
        out = json.loads(line)
        if "error" in out:
            raise EngineError(f"2D engine refused {next(iter(req))}: {out['error']}")
        out["ms"] = (time.perf_counter() - t0) * 1000
        return out

    def _open(self, encode: dict | None = None):
        comp = self.scene["comp"]
        key = (comp["props"]["width"], comp["props"]["height"], json.dumps(encode))
        if self._opened == key and encode is None:
            return
        req = {"width": comp["props"]["width"], "height": comp["props"]["height"],
               "html": stopgap_html.shell(comp)}
        if encode:
            req["encode"] = encode
        self._request({"open": req})
        self._opened = None if encode else key

    def load(self, scene: dict):
        frame_at(scene, 0.0)                         # a bad scene fails here, loudly
        self.scene = scene

    def _stage(self, t: float) -> str:
        if self.scene is None:
            raise EngineError("no scene loaded (Engine.load)")
        return stopgap_html.stage(frame_at(self.scene, t), self.caps)

    def still(self, t: float, png: Path) -> dict:
        self._open()
        png = Path(png)
        png.parent.mkdir(parents=True, exist_ok=True)
        out = self._request({"frame": {"stage": self._stage(t), "image": str(png)}})
        if not png.is_file():
            raise EngineError(f"2D engine said done but wrote no file: {png}")
        return out

    def video(self, mp4: Path, start: float = 0.0, end: float | None = None, progress=None) -> dict:
        p = self.scene["comp"]["props"]
        fps, end = p["fps"], p["duration"] if end is None else end
        mp4 = Path(mp4)
        mp4.parent.mkdir(parents=True, exist_ok=True)
        self._open(h264(mp4, p["width"], p["height"], fps))
        n = max(1, round((end - start) * fps))
        for i in range(n):
            self._request({"frame": {"stage": self._stage(start + i / fps), "index": i, "encode": True}})
            if progress:
                progress(i + 1, n)
        self._request({"finish": {}}, timeout_s=300.0)
        if not mp4.is_file() or mp4.stat().st_size == 0:
            raise EngineError(f"export wrote no video: {mp4}; log {self.log_path}")
        return {"file": str(mp4), "frames": n, "fps": fps}

    def close(self):
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
