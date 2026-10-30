"""A markup film drawn by the 2D engine's page path (rostrum2d-render serve: `open`, `frame {stage}`, `finish`;
apps/2d/engine/render/src/serve.rs). One engine process per Session; the page shell is sent again only when the
film's CSS or size changed. Looks and the export draw through the same requests (preview ≡ export, rule 6:
a frame the engine refuses fails loudly, naming the time)."""
from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

from .. import settings
from .film import Film
from .runner import script_error


class RenderError(RuntimeError):
    pass


class Session:
    def __init__(self, log: Path, encode: dict | None = None):
        exe = settings.engine_exe()
        if exe is None or not exe.is_file():
            raise RenderError("2D engine not found: " + ", ".join(map(str, settings.engine_candidates())))
        log.parent.mkdir(parents=True, exist_ok=True)
        self._log = open(log, "ab")
        self.proc = subprocess.Popen([str(exe), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self._log, creationflags=settings.NO_WINDOW)
        self.pid, self.encode, self._open = self.proc.pid, encode, None
        self._lock = threading.Lock()

    def request(self, req: dict, timeout_s: float = 120.0) -> dict:
        with self._lock:
            if self.proc.poll() is not None:
                raise RenderError(f"the 2D engine (pid {self.pid}) has stopped (exit {self.proc.returncode})")
            self.proc.stdin.write((json.dumps(req) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
        if not line:
            raise RenderError(f"the 2D engine (pid {self.pid}) ended without a reply")
        out = json.loads(line)
        if "error" in out:
            raise RenderError(out["error"])
        return out

    def page(self, film: Film):
        try:
            shell = film.shell()
        except Exception as e:
            raise RenderError(script_error(e, None)) from None
        want = (film.width, film.height, shell)
        if self._open == want:
            return
        req = {"width": film.width, "height": film.height, "html": shell}
        if self.encode:
            req["encode"] = self.encode
        self.request({"open": req})
        self._open = want

    def frame(self, film: Film, t: float, image: Path | None = None, encode: bool = False) -> dict:
        missing: list = []
        try:
            stage = film.markup(t, missing)
            samples = film.samples(t)
        except Exception as e:
            raise RenderError(script_error(e, t)) from None
        for m in dict.fromkeys(missing):
            note = f'keys name "#{m}", but no element has id="{m}"'
            if not any(n.startswith(note) for n in film.notes):
                note += f" (first at {t:.2f} s)"
                film.notes.append(note)
        req = {"stage": stage, "index": round(t * film.fps)}
        if samples:
            req["samples"] = samples
        if image is not None:
            req["image"] = str(image)
        if encode:
            req["encode"] = True
        try:
            return self.request({"frame": req})
        except RenderError as e:
            raise RenderError(f"frame at {t:.3f} s: {e}") from None

    def close(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=20)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()                 # our own child, by its handle
                self.proc.wait()
        self._log.close()


def stills(session: Session, film: Film, times: list[float], folder: Path) -> list[tuple[Path, float]]:
    session.page(film)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for t in times:
        p = folder / f"t{t:07.3f}.png"
        session.frame(film, t, p)
        out.append((p, t))
    return out


def h264(out: Path, film: Film, quality: str = "high") -> dict:
    """The engine's own MP4 writer (the operating system's H.264 encoder; never libx264, GPL), at a constant quality."""
    from ..io import formats
    q = {"draft": "standard", "standard": "standard", "high": "high"}[quality]
    rate = formats.rate(formats.get("mp4"), film.width, film.height, round(film.fps), q)
    exe = settings.engine_exe()
    return {"program": str(exe), "args": ["encode-mp4", str(out), str(film.width), str(film.height), f"{film.fps:g}",
                                          str(rate.kbps), str(rate.quality)]}


def export(film: Film, out: Path, log: Path, quality: str = "high", progress=None) -> dict:
    """Every frame into an MP4 at `out` (written as .partial, renamed only when whole)."""
    part = out.with_name(out.stem + ".partial" + out.suffix)
    part.unlink(missing_ok=True)
    s = Session(log, encode=h264(part, film, quality))
    t0 = time.perf_counter()
    n = max(1, round(film.duration * film.fps))
    try:
        s.page(film)
        for i in range(n):
            s.frame(film, i / film.fps, encode=True)
            if progress and i % 30 == 0:
                progress(i, n)
        r = s.request({"finish": {}}, timeout_s=600)
        if r.get("code", 0) != 0:
            raise RenderError(f"the encoder failed: {r}")
    finally:
        s.close()
    if not part.is_file() or part.stat().st_size == 0:
        raise RenderError(f"the export wrote no video at {part}")
    return {"frames": n, "seconds": round(time.perf_counter() - t0, 1), "partial": part}
