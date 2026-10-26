"""The screen tests' one stand-in for the sound engine (sound is checked by listening). It keeps the engine's writing
contract (ENGINE_CONTRACT.md § render): the mix is written under a part name, its levels (`<mix>.levels.json`, keyed
to the mix's size and time) are put beside it, and only then does the mix take its name, so whatever is announced is
whole. A stand-in that skipped the levels made the player say "no levels for this mix" whenever it got there in time.

    FakeEngine()                       a 10 ms silent render, at once
    FakeEngine(seconds=6, delay=0.8)   a longer one, taking a while (a long song's re-render)

`FAKE_PLAYER` is the player's stand-in (screensound/fake_play.py), which every screen test plays through (conftest.py):
a test never opens the machine's speakers, and the player reads the render and its levels as the engine's does.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 48000
FAKE_PLAYER = [sys.executable, "-I", str(Path(__file__).resolve().parents[1] / "screensound" / "fake_play.py")]


def write_render(out, seconds: float = 0.01, strips=("master",)):
    """A silent stereo float WAV at `out` with its levels beside it, the engine's way."""
    out = Path(out)
    part = out.with_name(out.name + ".partial")
    sf.write(part, np.zeros((max(1, round(RATE * seconds)), 2), "float32"), RATE, format="WAV", subtype="FLOAT")
    st = part.stat()
    hop = 1 / 30
    windows = [-1200, -1200] * max(1, round(seconds / hop))
    levels = {"contract": "rostrum-sound-levels/1", "mix": {"bytes": st.st_size, "modified": st.st_mtime},
              "hop": hop, "unit": "dB/10, [peak, rms] per window", "strips": {s: windows for s in strips}}
    side = out.with_suffix(".levels.json")
    side_part = side.with_name(side.name + ".partial")
    side_part.write_text(json.dumps(levels), encoding="utf-8")
    os.replace(side_part, side)
    os.replace(part, out)                           # last: the mix is seen only once all of it is there
    return out


class FakeEngine:
    def __init__(self, seconds: float = 0.01, delay: float = 0.0):
        self.seconds, self.delay = seconds, delay

    def request(self, do, schedule=None, out=None, **kw):
        if self.delay:
            time.sleep(self.delay)
        write_render(out, self.seconds)
        return {"file": out, "lufs": -20.0, "tracks": [], "stems": {}}

    def take_restarted(self):
        return ""

    def close(self):
        pass

    def abort(self):
        pass
