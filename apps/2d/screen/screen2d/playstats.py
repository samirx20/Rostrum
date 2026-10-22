"""Playback timing: how long each stage of a shown frame takes, and how many frames were shown per second.

On while `ROSTRUM2D_PLAYBACK_LOG=1` (one line per shown frame on stderr) or while the `play <seconds>` step measures
(steps.py). Stages: `gui` (the GUI thread's work per tick), `describe` (the scene for the engine), `load` (the scene
sent to the engine), `pixels` (the engine draws the frame), `image` (the frame copied into a picture).
"""
from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from contextlib import contextmanager


class PlayStats:
    def __init__(self):
        self.log = os.environ.get("ROSTRUM2D_PLAYBACK_LOG") == "1"
        self.on = self.log
        self.reset()

    def reset(self):
        self.ms, self.shown, self.t0 = defaultdict(list), 0, time.perf_counter()

    @contextmanager
    def stage(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            if self.on:
                self.ms[name].append((time.perf_counter() - t0) * 1000)

    def frame_shown(self, t: float):
        if not self.on:
            return
        self.shown += 1
        if self.log:
            last = "  ".join(f"{k} {v[-1]:.1f}" for k, v in self.ms.items() if v)
            print(f"play t={t:.3f} shown={self.shown}  {last} ms", file=sys.stderr)

    def report(self) -> str:
        secs = time.perf_counter() - self.t0
        stages = "  ".join(f"{k} {sum(v) / len(v):.1f} ms (×{len(v)})" for k, v in self.ms.items() if v)
        return f"shown {self.shown} frames in {secs:.2f} s = {self.shown / secs:.1f} fps;  {stages}"


STATS = PlayStats()
