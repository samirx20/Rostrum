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

import hashlib
import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LOG_DIR = Path.home() / ".rostrum" / "logs"
DEFAULT_LIBS = REPO / "proofs" / "3d-product" / ".build" / "cycles" / "lib" / "windows_x64"
FIXED_LIBS = Path(r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-product\.build\cycles\lib\windows_x64")
NEVER_LOAD = ("ffmpeg", "python")                      # GPL FFmpeg must never load; Python folders are not DLL folders


class EngineError(RuntimeError):
    pass


def find_exe() -> Path:
    """ROSTRUM3D_CORE, else this checkout's install."""
    if os.environ.get("ROSTRUM3D_CORE"):
        return Path(os.environ["ROSTRUM3D_CORE"])
    return REPO / "apps" / "3d" / "core" / ".build" / "install" / "rostrum3d-core.exe"


def library_bundle() -> Path:
    if os.environ.get("ROSTRUM3D_LIBS"):
        return Path(os.environ["ROSTRUM3D_LIBS"])
    return DEFAULT_LIBS if DEFAULT_LIBS.is_dir() else FIXED_LIBS


def runtime_env(base: dict | None = None) -> dict:
    """The child's environment: DLL folders on PATH, where Hydra finds the Cycles and stylized plug-ins, the GPU choice."""
    env = dict(os.environ if base is None else base)
    bundle = library_bundle()
    cycles = bundle.parents[1]                         # <cycles>/lib/windows_x64 -> <cycles>
    stylized = REPO / "proofs" / "3d-stylized" / ".build" / "install"
    dirs = [bundle / "usd" / "lib", *sorted(bundle.glob("*/bin")), cycles / "install"]
    dirs = [str(d) for d in dirs if d.is_dir() and not any(s in str(d).lower() for s in NEVER_LOAD)]
    env["PATH"] = os.pathsep.join(dirs + [env.get("PATH", "")])
    env["PXR_PLUGINPATH_NAME"] = os.pathsep.join(str(p) for p in (cycles / "install" / "hydra", stylized))
    env.setdefault("CYCLES_DEVICE", "OPTIX")
    return env


class Engine:
    def __init__(self, exe: Path | None = None, env: dict | None = None, args: tuple = ("serve",)):
        self.exe, self.args = (Path(exe) if exe else find_exe()), tuple(args)
        self._env = env
        self.proc, self.pid, self.log_path = None, None, None
        self._lines: queue.Queue = queue.Queue()
        self._hash, self._lock, self._notices = None, threading.RLock(), []
        self.restarts = 0

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
        if self.proc is None:
            self._start()
        elif self.proc.poll() is not None:
            code, old = self.proc.returncode, self.log_path
            self.restarts += 1
            self._start()
            self._notices.append(f"The 3D engine had stopped (exit {code}, log {old}); it was started again (pid {self.pid}) "
                                 "and the scene sent again.")

    def take_notices(self) -> list[str]:
        out, self._notices = self._notices, []
        return out

    def _request(self, req: dict, timeout_s: float = 120.0, progress=None) -> dict:
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
                    self.proc.kill()                    # our own child, by its handle; the next request starts a new one
                    self.proc.wait()
                    raise EngineError(f"3D engine took over {timeout_s:g} s for {name}; it was stopped; log {self.log_path}") from None
                if line is None:
                    raise EngineError(f"3D engine (pid {self.pid}) ended without a reply to {name}; it is started again on the "
                                      f"next request; log {self.log_path}")
                out = json.loads(line)
                if "ok" in out:
                    break
                if "progress" in out and progress:
                    try:
                        progress(out["progress"], out.get("of"), out)
                    except BaseException:               # a stop request: the render cannot be told to stop, so the process is
                        self.proc.kill()                # (our own child); the next request starts a new one
                        self.proc.wait()
                        raise
        if not out["ok"]:
            raise EngineError(f"3D engine refused {name}: {out.get('error', 'no reason given')}")
        out["ms"] = (time.perf_counter() - t0) * 1000
        return out

    # --- the requests
    def load(self, scene: dict) -> dict:
        out = self._request({"scene": scene})
        self._hash = hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest()
        return out

    def ensure_scene(self, scene: dict) -> bool:
        """Send the scene only when it differs from the one the engine holds. True when it was sent."""
        with self._lock:
            self._ensure_running()
            if hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest() == self._hash:
                return False
            self.load(scene)
            return True

    def render(self, progress=None, timeout_s: float | None = None, **req) -> dict:
        """One frame or `frames=[first, last]`; the files are checked here, so nothing is "done" without its file."""
        out = self._request({"render": {**req, "progress": progress is not None}},
                            timeout_s or float(req.get("timeoutS", 600)) + 60, progress)
        missing = [f[k] for f in out.get("frames", []) for k in ("exr", "png") if f.get(k) and not Path(f[k]).is_file()]
        if missing:
            raise EngineError(f"3D engine said done but wrote no file: {missing[0]}; log {self.log_path}")
        return out

    def pick(self, **req) -> dict:
        return self._request({"pick": req})

    def inspect_usd(self, file: str | Path) -> dict:
        return self._request({"inspect_usd": {"file": str(file)}})

    def save(self, file: str | Path, flatten: bool = False) -> dict:
        return self._request({"save": {"file": str(file), "flatten": flatten}})

    def info(self) -> dict:
        return self._request({"info": {}})

    def close(self):
        with self._lock:
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
