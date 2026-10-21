"""A thin Python handle on the archive's 2D renderer (`rostrum-motion serve`).

The renderer is one long-lived process: one JSON request per stdin line, one JSON reply per stdout line
(archive `native/rostrum-motion/src/serve.rs`). Python opens a page shell (styles, fonts, an empty
`<div id="rostrum-stage">`), then sends each frame's stage markup; Rust applies it to the kept page as edits,
lays it out (Blitz), paints it (Skia on the GPU) and writes a PNG or hands the pixels to ffmpeg itself.
Stdlib only.
"""
import json
import subprocess
import time
from pathlib import Path

EXE = Path(r"C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT\native\target\release\rostrum-motion.exe")


class RendererError(RuntimeError):
    pass


class Renderer:
    """One `rostrum-motion serve` process. Use as a context manager so the process always ends (by its own handle)."""

    def __init__(self, log: Path, exe: Path = EXE):
        if not exe.exists():
            raise RendererError(f"renderer not found: {exe}")
        self.log = open(log, "wb")
        self.proc = subprocess.Popen([str(exe), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log)
        self.pid = self.proc.pid

    def request(self, req: dict, timeout_s: float = 60.0) -> dict:
        line = (json.dumps(req) + "\n").encode("utf-8")
        t0 = time.perf_counter()
        self.proc.stdin.write(line)
        self.proc.stdin.flush()
        reply = self.proc.stdout.readline()
        if not reply:
            raise RendererError(f"renderer (pid {self.pid}) ended without a reply; see {self.log.name}")
        if time.perf_counter() - t0 > timeout_s:
            raise RendererError(f"renderer took longer than {timeout_s} s for {next(iter(req))}")
        out = json.loads(reply)
        if "error" in out:
            raise RendererError(f"renderer refused {next(iter(req))}: {out['error']}")
        out["roundTripMs"] = (time.perf_counter() - t0) * 1000.0
        return out

    def open(self, width: int, height: int, shell: str, encode: dict | None = None) -> dict:
        req = {"width": width, "height": height, "html": shell}
        if encode:
            req["encode"] = encode
        return self.request({"open": req})

    def still(self, stage: str, png: Path) -> dict:
        return self.request({"frame": {"stage": stage, "image": str(png)}})

    def encode_frame(self, stage: str, index: int) -> dict:
        return self.request({"frame": {"stage": stage, "index": index, "encode": True}})

    def finish(self) -> dict:
        return self.request({"finish": {}}, timeout_s=300.0)

    def peak_memory_mb(self) -> float:
        """The renderer's peak working set so far (Windows; GetProcessMemoryInfo)."""
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                               "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                               "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        c = Counters(cb=ctypes.sizeof(Counters))
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000 | 0x0010, False, self.pid)  # query limited information | vm read
        try:
            if not ctypes.WinDLL("psapi").GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
                raise RendererError(f"could not read the renderer's memory (pid {self.pid})")
        finally:
            k32.CloseHandle(h)
        return c.PeakWorkingSetSize / 2**20

    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()  # our own child, by its handle (pid self.pid)
                self.proc.wait()
        self.log.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def ffmpeg_h264(out: Path, width: int, height: int, fps: int) -> dict:
    """`open.encode`: the renderer starts ffmpeg itself and writes raw 8-bit straight RGBA frames to its stdin."""
    return {"program": "ffmpeg", "args": [
        "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", str(out)]}
