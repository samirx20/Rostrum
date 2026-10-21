"""The sound engine as one long-lived process (`rostrum-sound serve`, apps/sound/ENGINE_CONTRACT.md § 3).

Instruments, samples and decoded media stay loaded between requests, and the engine reuses each track's
render while its content is unchanged. An engine error comes back as the same RostrumError (code, where,
accepted, hint), so agents read the engine's words. A dead or silent engine is a loud error, never a hang.

    eng = Engine()                       # finds the built engine, or ROSTRUM_SOUND_ENGINE
    eng.request("render", schedule=..., out=r"C:\\...\\mix.wav", stems="all")
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from pathlib import Path

from rostrum_core import RostrumError, codes

from . import names
from .doc import fields_design as FDS

ENGINE_DIR = Path(__file__).resolve().parents[2] / "engine" / "target"
EXE = "rostrum-sound.exe" if os.name == "nt" else "rostrum-sound"
TIMEOUT_S = 600


def find_engine() -> Path:
    env = os.environ.get("ROSTRUM_SOUND_ENGINE")
    found = [Path(env)] if env else [ENGINE_DIR / p / EXE for p in ("release", "agent")]
    for p in found:
        if p.is_file():
            return p
    raise RostrumError(codes.INTERNAL, "sound engine", "rostrum-sound", "is not built",
                       [str(p) for p in found], "Build it: cargo build --profile agent -j 4 in apps/sound/engine, or set ROSTRUM_SOUND_ENGINE.")


class Engine:
    def __init__(self, exe: Path | None = None):
        self.exe = Path(exe) if exe else find_engine()
        self._proc: subprocess.Popen | None = None
        self._lines: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._n = 0

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    def _start(self):
        self._proc = subprocess.Popen([str(self.exe), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        self._lines = queue.Queue()
        threading.Thread(target=self._read, args=(self._proc, self._lines), daemon=True).start()
        self._stderr: list[str] = []
        threading.Thread(target=self._drain, args=(self._proc, self._stderr), daemon=True).start()

    @staticmethod
    def _read(proc, lines):
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    @staticmethod
    def _drain(proc, keep):
        for line in proc.stderr:
            keep.append(line.rstrip())
            del keep[:-40]

    def request(self, do: str, timeout: float = TIMEOUT_S, **fields) -> dict:
        """One request; its `result`, or the engine's error raised as a RostrumError."""
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._start()
            self._n += 1
            req = {"id": self._n, "do": do, **fields}
            try:
                self._proc.stdin.write(json.dumps(req, default=str) + "\n")
                self._proc.stdin.flush()
                line = self._lines.get(timeout=timeout)
            except queue.Empty:
                self.close()
                raise RostrumError(codes.RENDER_FAILED, f"sound engine › {do}", "the engine", f"did not answer within {timeout:.0f} s; it was stopped") from None
            except OSError as e:
                line = None
                err = e
            if line is None:
                tail = "\n".join(self._stderr[-10:]) if hasattr(self, "_stderr") else ""
                self._proc = None
                raise RostrumError(codes.INTERNAL, f"sound engine › {do}", "the engine", f"stopped unexpectedly: {tail or locals().get('err', 'no output')}")
        reply = json.loads(line)
        if reply.get("id") != req["id"]:
            raise RostrumError(codes.INTERNAL, f"sound engine › {do}", "the engine", f"answered request {reply.get('id')} instead of {req['id']}")
        if not reply["ok"]:
            e = reply["error"]
            code = e["code"] if e["code"] in vars(codes).values() else codes.INTERNAL
            raise RostrumError(code, f"sound engine › {e['where']}", e["subject"], e["problem"], e.get("accepted") or (), e.get("hint") or None)
        return reply["result"]

    def close(self):
        """Ends the engine process this object started (by its own handle, never by name)."""
        p, self._proc = self._proc, None
        if p and p.poll() is None:
            try:
                p.stdin.write(json.dumps({"do": "quit"}) + "\n")
                p.stdin.flush()
                p.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                p.kill()
                p.wait(timeout=5)

    def check_names(self) -> list[str]:
        """Differences between names.py and the engine's `describe` (the authority); empty when they agree."""
        d = self.request("describe")
        pairs = {"tones": names.TONES, "spaces": names.SPACES, "eqShapes": names.EQ_SHAPES, "builtIns": names.BUILT_INS,
                 "synthDrums": names.SYNTH_DRUMS, "gmDrums": names.GM_DRUMS}
        out = []
        for key, ours in pairs.items():
            theirs = [g["name"] for g in d[key]] if key == "gmDrums" else d[key]
            if sorted(ours) != sorted(theirs):
                out.append(f"{key}: python {sorted(set(ours) ^ set(theirs))} differ from the engine")
        out += FDS.differences(d.get("designs", {}))
        if d["contract"] != names.CONTRACT:
            out.append(f"contract: python {names.CONTRACT}, engine {d['contract']}")
        return out

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
