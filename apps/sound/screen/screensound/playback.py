"""What you hear: the document rendered by the sound engine (the same path as export: preview ≡ export), off the
GUI thread, newest request wins. The render file is what the engine's live transport plays (live_transport.py).

`Renderer`: one worker thread owns one long-lived engine process (rostrum_sound.engine.Engine, which reuses each
unchanged track's render, so a re-render after a small edit is quick); each render goes to a new numbered file
(the player may still hold the last one open), with stems for every track so the Mix page has meters. A failed
render is reported (`failed`), never passed off as the new sound; the last good render stays playable.
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from rostrum_core import scratch
from rostrum_sound import settings

SCRATCH = settings.cache_dir() / "screensound" / str(os.getpid())
KEEP = 2                     # renders kept on disk: the newest and the one that may still be playing


def open_engine():
    """The engine the screen renders with (swap here, nowhere else)."""
    from rostrum_sound.engine import Engine
    return Engine()


class Renderer(QObject):
    rendered = Signal("QVariantMap")     # the engine's render answer (ENGINE_CONTRACT.md § 3)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cv = threading.Condition()
        self._pending, self._busy, self._stop, self._serial = None, False, False, 0
        self._eng = None                 # the worker's engine (close() aborts a render still running on it)
        SCRATCH.mkdir(parents=True, exist_ok=True)
        scratch.sweep_later(SCRATCH.parent)      # folders killed runs left (a day old, no process owns): once, well after the start
        self._thread = threading.Thread(target=self._run, name="render-sound", daemon=True)
        self._thread.start()

    def request(self, schedule: dict):
        with self._cv:
            self._pending = schedule
            self._cv.notify()

    def idle(self) -> bool:
        with self._cv:
            return self._pending is None and not self._busy

    def _run(self):
        try:
            while True:
                with self._cv:
                    while self._pending is None and not self._stop:
                        self._cv.wait()
                    if self._stop:
                        return
                    schedule, self._pending, self._busy = self._pending, None, True
                try:
                    eng = self._eng = self._eng or open_engine()
                    self._serial += 1
                    out = SCRATCH / f"play-{self._serial}.wav"
                    result = eng.request("render", schedule=schedule, out=str(out), stems="all")
                    if not Path(result.get("file", "")).is_file():
                        raise RuntimeError(f"the engine answered but wrote no file at {out}")
                    self._tidy()
                    note = eng.take_restarted()          # the engine died during it and was started again
                    self.rendered.emit({**result, "restarted": note} if note else result)
                except Exception as e:  # noqa: BLE001  any failure is reported, loudly
                    if self._stop:       # closed mid-render (close() aborted the engine): nobody waits for it
                        return
                    line = f"Error: render: {getattr(e, 'line', lambda: e)()}"
                    print(line, file=sys.stderr)
                    self.failed.emit(line)
                finally:
                    with self._cv:
                        self._busy = False
        finally:
            if self._eng is not None:
                self._eng.close()

    def _tidy(self):
        """Delete renders older than the last KEEP (files and their stems folders)."""
        for p in SCRATCH.glob("play-*"):
            n = p.name.split("-", 1)[1].split(".", 1)[0]
            if n.isdigit() and int(n) <= self._serial - KEEP:
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)

    def close(self):
        with self._cv:
            self._stop = True
            running = self._eng if self._busy else None
            self._cv.notify()
        if running is not None:          # a render still running is for a song being closed: stop it, don't wait
            running.abort()
        self._thread.join(timeout=30)
        for _ in range(20):          # a file another reader still holds is let go a moment later (Windows)
            shutil.rmtree(SCRATCH, ignore_errors=True)
            if not SCRATCH.exists():
                return
            time.sleep(0.1)
        print(f"Warning: could not delete the screen's renders in {SCRATCH} (a file is still open)", file=sys.stderr)
