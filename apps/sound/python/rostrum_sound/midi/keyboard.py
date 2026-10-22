"""Recording from a MIDI keyboard: the engine's `rostrum-sound live <instrument.json> --midi <n> --shared` run as a
process (its PID kept, ended by that PID), its {"note": …} lines collected, and the take put on a track as ONE
operation (`note.add_many`, or `hit.add_many` on a drum track) at the time the take started (one undo step).

    devices()                                   # the keyboards' names, by index
    take = Take(track, device=0); take.start()  # returns once the engine is ready (or raises, saying why)
    ... take.poll()                             # the notes finished so far: [{key, velocity, start, end}, …]
    call = take_call(track, take.stop(), at, root)

What you hear while playing is a monitor (`monitor_spec`): an SFZ track plays its own file, any other track a plain
synth; the render plays the track's real instrument. Note times are seconds since the engine's stream started
(as heard), so a take lands where it was played relative to the press of Record.
"""
from __future__ import annotations

import json
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from rostrum_core import RostrumError, codes

from .. import settings
from ..doc import tempo
from ..engine import find_engine
from .song import GM_TO_SYNTH

READY_S = 8         # winmm can take seconds to load the first time
QUIT_S = 5
WAVES = ("sine", "saw", "square", "triangle")


def _fail(problem, hint=""):
    return RostrumError(codes.INTERNAL, "keyboard take", "the MIDI keyboard", problem, [], hint)


def devices(exe=None) -> list[str]:
    """The MIDI input devices' names (index = the device number); [] when none is connected."""
    r = subprocess.run([str(exe or find_engine()), "midi"], capture_output=True, text=True, encoding="utf-8",
                       timeout=20)
    if r.returncode != 0:
        raise _fail(f"`rostrum-sound midi` failed (exit {r.returncode}): {r.stderr.strip() or '(nothing on stderr)'}")
    return list(json.loads(r.stdout.strip().splitlines()[-1]).get("devices", []))


def monitor_spec(track: dict) -> dict:
    if track.get("instrument") == "sfz" and track.get("sfz"):
        return {"sfz": {"file": track["sfz"], "legato": bool(track.get("legato")), "swell": bool(track.get("swell"))}}
    wave = track.get("synth") if track.get("synth") in WAVES else "sine"
    return {"synth": {"wave": wave, "voices": 1, "detune": 0, "cutoff": 6000, "resonance": 0.1, "envAmount": 0,
                      "attack": 0.004, "decay": 0.3, "sustain": 0.7, "release": 0.15, "octave": 0, "width": 0}}


def parse(lines) -> tuple[dict | None, list[dict], list[str]]:
    """(the ready line, the finished notes, the engine's errors) from the engine's output lines (the parsing seam)."""
    ready, notes, errors = None, [], []
    for line in lines:
        try:
            e = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if "ready" in e:
            ready = e["ready"]
        elif "note" in e:
            notes.append(e["note"])
        elif "error" in e:
            errors.append(str(e["error"]))
    return ready, notes, errors


class Take:
    def __init__(self, track: dict, device: int = 0, command: list[str] | None = None):
        self.spec_file = Path(tempfile.mkdtemp(prefix="rostrum-keys-")) / "instrument.json"
        self.spec_file.write_text(json.dumps(monitor_spec(track)), encoding="utf-8")
        self.command = command or [str(find_engine()), "live", str(self.spec_file), "--midi", str(device), "--shared"]
        self.ready, self.notes, self.errors, self.pid = None, [], [], None
        self._lines: queue.Queue = queue.Queue()
        self._proc: subprocess.Popen | None = None

    def start(self):
        try:
            self._start()
        finally:                            # the engine has read its instrument once it is ready (or failed)
            self.spec_file.unlink(missing_ok=True)
            self.spec_file.parent.rmdir()

    def _start(self):
        self._proc = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                      env=settings.engine_env())
        self.pid, self._err = self._proc.pid, []
        threading.Thread(target=lambda: [self._lines.put(x) for x in self._proc.stdout], daemon=True).start()
        threading.Thread(target=lambda: self._err.extend(self._proc.stderr), daemon=True).start()
        end = time.monotonic() + READY_S
        while self.ready is None:
            self.poll(check=False)
            if self._proc.poll() is not None and self._lines.empty():
                raise self._ended("the engine stopped before the keyboard was ready")
            if time.monotonic() > end:
                self.kill()
                raise _fail(f"the keyboard was not ready in {READY_S} s", "Is it connected? `rostrum-sound midi` lists them.")
            time.sleep(0.01)

    def poll(self, check=True) -> list[dict]:
        lines = []
        while not self._lines.empty():
            lines.append(self._lines.get_nowait())
        ready, notes, errors = parse(lines)
        self.ready = ready or self.ready
        self.notes += notes
        self.errors += errors
        if check and self._proc.poll() not in (None, 0):
            raise self._ended("the engine stopped during the take")
        return list(self.notes)

    def stop(self) -> list[dict]:
        """End the take (keys still down are released) and return its notes; loud when the engine failed."""
        try:
            self._proc.stdin.write('{"quit": true}\n')
            self._proc.stdin.flush()
            self._proc.stdin.close()
        except OSError:
            pass
        try:
            self._proc.wait(QUIT_S)
        except subprocess.TimeoutExpired:
            self.kill()
            raise _fail(f"the engine did not end the take in {QUIT_S} s") from None
        time.sleep(0.05)
        self.poll(check=False)
        if self._proc.returncode != 0:
            raise self._ended("the engine failed")
        return list(self.notes)

    def kill(self):
        """End the engine process this take started (its own handle, by its PID)."""
        if self._proc and self._proc.poll() is None:
            self._proc.kill()
            self._proc.wait()

    def _ended(self, what):
        time.sleep(0.1)
        said = "".join(self._err).strip() or "; ".join(self.errors) or "(nothing on stderr)"
        return _fail(f"{what} (exit code {self._proc.returncode}): {said}")


def take_call(track: dict, notes: list[dict], at: float, root: dict, grid: float | None = None) -> dict | None:
    """The one call that puts a take on `track`, a note's time `at + start` seconds (`at` = the timeline time of the
    engine's stream start): notes in beats (they follow the tempo map), or drum hits on a drum track (keys the synth
    kit has no drum for are left out). `grid` (beats): starts and ends snap to it (quantize). Notes before the song's
    start are left out. None when nothing was played."""
    notes = [n for n in notes if at + n["start"] >= 0]

    def beat(sec):
        b = tempo.beat_at(root, at + sec)
        return round(round(b / grid) * grid if grid else b, 4)
    if track.get("instrument") in ("kit", "kitSfz"):
        hits = [{"drum": GM_TO_SYNTH[n["key"]] if track["instrument"] == "kit" else n["key"],
                 "at": {"beat": beat(n["start"])}, "vel": round(min(1.0, n["velocity"]), 3)}
                for n in notes if track["instrument"] == "kitSfz" or n["key"] in GM_TO_SYNTH]
        return {"op": "hit.add_many", "target": [track["id"]], "args": {"hits": hits}} if hits else None
    out = [{"pitch": int(n["key"]), "at": {"beat": beat(n["start"])},
            "dur": {"beats": max(grid or 0.01, round(beat(n["end"]) - beat(n["start"]), 4))},
            "vel": round(min(1.0, n["velocity"]), 3)} for n in notes]
    return {"op": "note.add_many", "target": [track["id"]], "args": {"notes": out}} if out else None
