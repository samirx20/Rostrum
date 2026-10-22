"""The sound engine as one long-lived process (`rostrum-sound serve`, apps/sound/ENGINE_CONTRACT.md § 3).

Instruments, samples and decoded media stay loaded between requests, and the engine reuses each track's
render while its content is unchanged. An engine error comes back as the same RostrumError (code, where,
accepted, hint), so agents read the engine's words. A dead or silent engine is a loud error, never a hang.

    eng = Engine()                       # finds the engine (settings.engine_path), or ROSTRUM_SOUND_ENGINE
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

from . import names, settings
from .doc import fields_design as FDS

TIMEOUT_S = 600


def find_engine() -> Path:
    """The engine program (settings.engine_path: the one place it is looked for)."""
    return settings.engine_path()


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
        try:
            reply = json.loads(line)
        except json.JSONDecodeError:
            raise RostrumError(codes.INTERNAL, f"sound engine › {do}", "the engine",
                               f"answered with something that is not an answer: {line.strip()[:160]!r}") from None
        if reply.get("id") != req["id"]:
            raise RostrumError(codes.INTERNAL, f"sound engine › {do}", "the engine", f"answered request {reply.get('id')} instead of {req['id']}")
        if not reply["ok"]:
            e = reply["error"]
            code = e["code"] if e["code"] in vars(codes).values() else codes.INTERNAL
            raise RostrumError(code, f"sound engine › {e['where']}", e["subject"], e["problem"], e.get("accepted") or (), e.get("hint") or None)
        if do == "render":                   # the engine's cache files grew: keep the one cache under its cap
            from . import cache_cap
            cache_cap.after_render()
        return reply["result"]

    def plugins(self, path: str | None = None) -> dict:
        """The CLAP / VST3 plug-ins installed (or those in `path`, a file or folder): {folders, plugins: [{format,
        path, id, name, vendor, kind: "effect" | "instrument", hasWindow, params: [{id, name, min, max, default}]}],
        failed: [{format, path, error}]}."""
        return self.request("plugins", **({"path": str(path)} if path else {}))

    def plugin_window(self, spec: dict, timeout: float = 3600) -> dict:
        """Open the plug-in's own window; returns {state, params} when the person closes it (waits that long:
        run it off the screen's thread). `spec` is the document's plugin record."""
        from .doc import plugins
        return self.request("pluginWindow", timeout=timeout, plugin=plugins.engine_form(spec))

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
