"""Recording a take from the microphone: the engine's `rostrum-sound record <out.wav>` run as a process.

    rec = Recorder(take_path(doc, "voice"))
    rec.start()                          # returns once the microphone runs (or raises, saying why)
    ... rec.poll() -> [(seconds, peakDb), ...] since the last call (a meter)
    wav = rec.stop()                     # the WAV's path; raises when the engine failed or sent no `done`
    doc.apply([take_call("voice", wav, at)], "agent")      # the take is a clip: one operation, one undo step

`land_take` puts a take of the engine's live transport (the screen's, sample-placed) on a track.
`record_take(doc, track, at, seconds)` does all of it for a script. Nothing here captures audio itself.
Takes go in `<project folder>/media/` (a document without a folder: `./takes/`), named `<track name>-take-<n>.wav`.
"""
from __future__ import annotations

import json
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

from rostrum_core import RostrumError, codes

from . import settings
from .deliver import safe_name
from .engine import find_engine

READY_S = 6          # the microphone must be running by then
DONE_S = 15          # after `stop`, the file must be written by then


def _fail(problem, hint=""):
    return RostrumError(codes.INTERNAL, "record", "the microphone take", problem, [], hint)


def take_path(doc, track_id: str) -> Path:
    """The next free `<track name>-take-<n>.wav` in the project's media folder (made when missing). The name is the
    track's own name as the person sees it ("Recording", "Vocals"), made safe as a file name; the id when it has none."""
    folder = (Path(doc.folder) / "media") if getattr(doc, "folder", None) else Path.cwd() / "takes"
    folder.mkdir(parents=True, exist_ok=True)
    item = doc.item(track_id) if doc.has(track_id) else None
    stem = safe_name((item or {}).get("name") or track_id, set()).replace(".", "-")
    n = 1
    while (folder / f"{stem}-take-{n}.wav").exists():
        n += 1
    return folder / f"{stem}-take-{n}.wav"


def take_call(track_id: str, wav, at) -> dict:
    """The one operation that puts a take on a track at time `at`."""
    return {"op": "clip.add", "target": [track_id], "args": {"media": str(wav), "at": at}}


def land_take(doc, track_id: str, take: dict) -> dict:
    """The one `clip.add` for a take the engine's live transport recorded (its `{"take": {file, start, …}}` line,
    `rostrum-sound play --mic`): the file moves to the project's media folder (`take_path`) and the clip starts at
    the take's `start`, already the mix time heard with it (the engine's clock, minus the microphone's calibrated
    delay). A take whose start the delay put before the song's start is trimmed with the in-point."""
    src = Path(take.get("file", ""))
    if not src.is_file():
        raise _fail(f"the engine reported a take at {src} but there is no file there")
    dest = take_path(doc, track_id)
    shutil.move(str(src), dest)
    start = float(take["start"])
    args = {"media": str(dest), "at": round(max(0.0, start), 4)}
    if start < 0:
        args["in"] = round(-start, 4)
    return {"op": "clip.add", "target": [track_id], "args": args}


class Recorder:
    """One take. `command` is the process to run; the default is the engine's `record` (tests may swap in a
    stand-in that speaks the same lines: that is the only seam)."""

    def __init__(self, out, seconds: float | None = None, command: list[str] | None = None):
        self.out = Path(out)
        self.command = command or [str(find_engine()), "record", str(self.out)] + (["--seconds", str(seconds)] if seconds else [])
        self.device, self.rate, self.done = "", 0, None
        self._events: queue.Queue = queue.Queue()
        self._proc: subprocess.Popen | None = None

    @property
    def running(self) -> bool:
        return self._proc is not None and self.done is None and self._proc.poll() is None

    def start(self):
        self._proc = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, encoding="utf-8", env=settings.engine_env())
        self._err: list[str] = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=lambda: self._err.extend(self._proc.stderr), daemon=True).start()
        end = time.monotonic() + READY_S
        while not self.rate:
            self._drain()
            if self._proc.poll() is not None and self._events.empty():
                raise self._ended("the engine stopped before the microphone was running")
            if time.monotonic() > end:
                self.kill()
                raise _fail(f"the microphone did not start in {READY_S} s", "Is one connected, and allowed in Windows privacy settings?")
            time.sleep(0.01)

    def _read(self):
        for line in self._proc.stdout:
            try:
                self._events.put(json.loads(line))
            except json.JSONDecodeError:
                pass
        self._events.put(None)

    def _drain(self) -> list[tuple[float, float]]:
        levels = []
        while True:
            try:
                e = self._events.get_nowait()
            except queue.Empty:
                return levels
            if e is None:
                continue
            if "ready" in e:
                self.rate, self.device = e["ready"]["rate"], e["ready"]["device"]
            elif "level" in e:
                levels.append((e["level"]["t"], e["level"]["peakDb"]))
            elif "done" in e:
                self.done = e["done"]

    def poll(self) -> list[tuple[float, float]]:
        """The meter readings (seconds into the take, peak dBFS) since the last call. Raises when the engine died."""
        levels = self._drain()
        if self._proc.poll() not in (None, 0) and self.done is None:
            raise self._ended("the engine stopped during the take")
        return levels

    def stop(self) -> Path:
        """End the take and return the WAV; loud when the engine failed or never said it was done."""
        try:
            self._proc.stdin.write("stop\n")
            self._proc.stdin.flush()
        except OSError:
            pass                                    # already ending; the exit code below says why
        end = time.monotonic() + DONE_S
        while self._proc.poll() is None and time.monotonic() < end:
            time.sleep(0.02)
        if self._proc.poll() is None:
            self.kill()
            raise _fail(f"the engine did not finish the take in {DONE_S} s")
        time.sleep(0.05)
        self._drain()
        if self._proc.returncode != 0:
            raise self._ended("the engine failed")
        if self.done is None:
            raise _fail("the engine ended without saying the take was done")
        if not Path(self.done["file"]).is_file():
            raise _fail(f'the take file {self.done["file"]} was not written')
        return Path(self.done["file"])

    def kill(self):
        if self._proc and self._proc.poll() is None:
            self._proc.kill()
            self._proc.wait()

    def _ended(self, what):
        time.sleep(0.1)
        said = "".join(self._err).strip() or "(nothing on stderr)"
        return _fail(f"{what} (exit code {self._proc.returncode}): {said}")


def record_take(doc, track_id: str, at, seconds: float, who="script"):
    """For scripts and agents: record `seconds` from the microphone onto `track_id` at `at`; returns the clip's WAV."""
    rec = Recorder(take_path(doc, track_id), seconds)
    rec.start()
    end = time.monotonic() + seconds + 1
    while rec.running and time.monotonic() < end:
        rec.poll()
        time.sleep(0.05)
    wav = rec.stop()
    doc.apply([take_call(track_id, wav, at)], who, label="Record take")
    return wav
