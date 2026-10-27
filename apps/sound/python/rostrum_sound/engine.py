"""The sound engine as one long-lived process (`rostrum-sound serve`, apps/sound/ENGINE_CONTRACT.md § 3).

Instruments, samples and decoded media stay loaded between requests, and the engine reuses each track's
render while its content is unchanged. An engine error comes back as the same RostrumError (code, where,
accepted, hint), so agents read the engine's words. A dead or silent engine is a loud error, never a hang.

    eng = Engine()                       # finds the engine (settings.engine_path), or ROSTRUM_SOUND_ENGINE
    eng = Engine(background=True)        # below the screen's priority: a render never takes a frame from the window
    eng.request("render", schedule=..., out=r"C:\\...\\mix.wav", stems="all")
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from rostrum_core import RostrumError, codes

from .engine_words import plain_where

from . import names, settings

TIMEOUT_S = 600
NOT_TWICE = ("pluginWindow",)        # a request that shows the person something is not repeated behind their back
WORDS = {"render": "a render", "play": "playback"}
BELOW_NORMAL = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)   # Windows; elsewhere a nice value (_start)


def find_engine() -> Path:
    """The engine program (settings.engine_path: the one place it is looked for)."""
    return settings.engine_path()


class Engine:
    def __init__(self, exe: Path | None = None, background: bool = False):
        self.exe = Path(exe) if exe else find_engine()
        self.background = background         # a screen's renders: the engine runs below normal priority (_lower)
        self._proc: subprocess.Popen | None = None
        self._lines: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._n = 0
        self._err, self.restarted = "", ""
        self._aborted = False                # abort(): this engine is done; nothing starts it again

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    def _start(self):
        self._proc = subprocess.Popen([str(self.exe), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
                                      creationflags=BELOW_NORMAL if self.background else 0)
        if self.background and sys.platform != "win32":
            os.setpriority(os.PRIO_PROCESS, self._proc.pid, 10)
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
        """One request; its `result`, or the engine's error raised as a RostrumError. An engine found dead is
        started again (one log line); one that dies during a request is started again and asked once more."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is not None:
                self._log(f"the sound engine stopped (exit code {self._proc.returncode}) and was restarted")
            self._n += 1
            req = {"id": self._n, "do": do, **fields}
            line = self._ask(req, timeout)
            if line is None and self._aborted:
                raise RostrumError(codes.INTERNAL, f"sound engine › {do}", "the engine", "was stopped (abort)")
            if line is None and do not in NOT_TWICE:
                self._log(f"the sound engine stopped (exit code {self._code()}) during {do!r} and was restarted; "
                          "asked again")
                self.restarted = f"The sound engine stopped during {WORDS.get(do, 'its work')} and was restarted. Nothing was lost."
                line = self._ask(req, timeout)
            if line is None:
                tail = "\n".join(self._stderr[-10:]) if hasattr(self, "_stderr") else ""
                code, self._proc = self._code(), None
                raise RostrumError(codes.INTERNAL, f"sound engine › {do}", "the engine",
                                   f"stopped unexpectedly (exit code {code}): {tail or self._err or 'no output'}")
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
            raise RostrumError(code, plain_where(e["where"], req), e["subject"], e["problem"], e.get("accepted") or (), e.get("hint") or None)
        if do in ("render", "measure"):      # the engine's cache files grew: keep the one cache under its cap
            from . import cache_cap
            cache_cap.after_render()
        return reply["result"]

    def _ask(self, req: dict, timeout: float):
        """Send one request (starting the engine if needed) and wait for its line; None if the engine died."""
        if self._aborted:
            return None
        if self._proc is None or self._proc.poll() is not None:
            self._start()
        self._err = ""
        try:
            self._proc.stdin.write(json.dumps(req, default=str) + "\n")
            self._proc.stdin.flush()
            return self._lines.get(timeout=timeout)
        except queue.Empty:
            self.close()
            raise RostrumError(codes.RENDER_FAILED, f"sound engine › {req['do']}", "the engine",
                               f"did not answer within {timeout:.0f} s; it was stopped") from None
        except OSError as e:
            self._err = str(e)
            return None

    def _code(self):
        try:
            return self._proc.wait(timeout=2) if self._proc else None
        except subprocess.TimeoutExpired:
            return "still running"

    def take_restarted(self) -> str:
        """The plain sentence about a restart during the last requests (once), else ""."""
        note, self.restarted = self.restarted, ""
        return note

    @staticmethod
    def _log(line: str):
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}", file=sys.stderr, flush=True)   # the app's log

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

    def abort(self):
        """Ends the engine process now, even mid-request, from any thread (a screen closing a song does not wait for a
        render nobody will hear): the waiting request fails at once and the engine is never started again."""
        self._aborted = True
        p = self._proc
        if p and p.poll() is None:
            p.kill()
            p.wait(timeout=5)

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

    def can(self, do: str) -> bool:
        """Whether this engine answers the request `do` (its `describe` lists `requests`; an engine older than that
        list answers only what every engine did). Asked once per engine process."""
        if getattr(self, "_can", (None,))[0] != self.pid or self.pid is None:
            got = self.request("describe").get("requests")
            self._can = (self.pid, set(got) if got else {"describe", "check", "render", "range", "plugins", "pluginWindow", "quit"})
        return do in self._can[1]

    def check_names(self) -> list[str]:
        """Differences between names.py and the engine's `describe` (the authority); empty when they agree."""
        d = self.request("describe")
        pairs = {"tones": names.TONES, "spaces": names.SPACES, "eqShapes": names.EQ_SHAPES, "builtIns": names.BUILT_INS,
                 "synthDrums": names.SYNTH_DRUMS, "gmDrums": names.GM_DRUMS, "kitNames": names.KITS}
        out = []
        for key, ours in pairs.items():
            if key not in d:
                continue
            theirs = [g["name"] for g in d[key]] if key == "gmDrums" else d[key]
            if sorted(ours) != sorted(theirs):
                out.append(f"{key}: python {sorted(set(ours) ^ set(theirs))} differ from the engine")
        if d["contract"] != names.CONTRACT:
            out.append(f"contract: python {names.CONTRACT}, engine {d['contract']}")
        return out

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
