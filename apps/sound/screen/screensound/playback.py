"""What you hear: the document rendered by the sound engine (the same path as export: preview ≡ export), off the
GUI thread, newest request wins. The render file is what the engine's live transport plays (live_transport.py).

`Renderer`: one worker thread owns one long-lived engine process (rostrum_sound.engine.Engine, which reuses each
unchanged track's render, so a re-render after a small edit is quick); each render goes to a new numbered file
(the player may still hold the last one open), with stems for every track so the Mix page has meters. A failed
render is reported (`failed`), never passed off as the new sound; the last good render stays playable.
`Player`: QMediaPlayer + QAudioOutput, only for auditioning a library sound in its own format (library_panel.py);
the song itself plays through the engine. With no sound output it says so and runs on a clock.
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal

SCRATCH = Path.home() / ".rostrum" / "cache" / "screensound" / str(os.getpid())
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
        SCRATCH.mkdir(parents=True, exist_ok=True)
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
        eng = None
        try:
            while True:
                with self._cv:
                    while self._pending is None and not self._stop:
                        self._cv.wait()
                    if self._stop:
                        return
                    schedule, self._pending, self._busy = self._pending, None, True
                try:
                    eng = eng or open_engine()
                    self._serial += 1
                    out = SCRATCH / f"play-{self._serial}.wav"
                    result = eng.request("render", schedule=schedule, out=str(out), stems="all")
                    if not Path(result.get("file", "")).is_file():
                        raise RuntimeError(f"the engine answered but wrote no file at {out}")
                    self._tidy()
                    self.rendered.emit(result)
                except Exception as e:  # noqa: BLE001  any failure is reported, loudly
                    line = f"Error: render: {getattr(e, 'line', lambda: e)()}"
                    print(line, file=sys.stderr)
                    self.failed.emit(line)
                finally:
                    with self._cv:
                        self._busy = False
        finally:
            if eng is not None:
                eng.close()

    def _tidy(self):
        """Delete renders older than the last KEEP (files and their stems folders)."""
        for p in SCRATCH.glob("play-*"):
            n = p.name.split("-", 1)[1].split(".", 1)[0]
            if n.isdigit() and int(n) <= self._serial - KEEP:
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)

    def close(self):
        with self._cv:
            self._stop = True
            self._cv.notify()
        self._thread.join(timeout=30)
        for _ in range(20):          # a file another reader still holds is let go a moment later (Windows)
            shutil.rmtree(SCRATCH, ignore_errors=True)
            if not SCRATCH.exists():
                return
            time.sleep(0.1)
        print(f"Warning: could not delete the screen's renders in {SCRATCH} (a file is still open)", file=sys.stderr)


class Player(QObject):
    """Plays one file from a time. `position()` is where it is, in seconds (the player's, or the clock's)."""
    problem = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
        self.has_output = bool(QMediaDevices.audioOutputs())
        self._player = QMediaPlayer(self)
        self._out = QAudioOutput(self)
        self._player.setAudioOutput(self._out)
        self._player.errorOccurred.connect(lambda _e, text: self.problem.emit(f"Error: playback: {text}"))
        self._file, self._t0, self._clock, self.playing = "", 0.0, 0.0, False

    def play(self, file: str, t: float):
        self._t0, self._clock, self.playing = t, time.monotonic(), True
        if not self.has_output:
            return
        if file != self._file:
            self._file = file
            self._player.setSource(QUrl.fromLocalFile(file))
        self._player.setPosition(int(t * 1000))
        self._player.play()

    def stop(self):
        self.playing = False
        if self.has_output:
            self._player.stop()

    def position(self) -> float:
        from PySide6.QtMultimedia import QMediaPlayer
        playing = self.has_output and self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        if playing and self._player.position() > 0:      # a device that never starts moving: the clock runs on
            return self._player.position() / 1000
        return self._t0 + time.monotonic() - self._clock

    def close(self):
        self.stop()
        self._player.setSource(QUrl())
