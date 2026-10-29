"""A pose drag's solving, off the screen's thread (pose_drag.py). The pointer's move only hands over its newest spot
(`aim`); one worker thread takes the newest spot waiting (older ones are dropped: the drag follows the pointer, never
a queue of stale moves), solves the turns (pose_link.solve), makes the `clay_pose` payload and the overlay's lines,
dots and rings for those turns, and hands the result back (`done`, called on the worker: pose_qt's signal carries it to
the screen's thread). Each result has its spot's number, so the drop knows when the last one is in, and the time each
part took. A new drag (`start`) or `stop` makes every result of the drag before stale. No Qt.
"""
from __future__ import annotations

import threading
import time

from . import gizmo as G, pose_link as L, pose_view as PV
from rostrum3d import aim


class Solver:
    def __init__(self, done):
        self._done, self._cv = done, threading.Condition()
        self._job, self._spot, self._gen, self._closed = None, None, 0, False
        self._thread = threading.Thread(target=self._run, name="pose-solver", daemon=True)
        self._thread.start()

    def start(self, job: dict) -> int:
        """A new drag: {clay, bone, local, point, world, view, held, holds, t, w, h, layer, stack}. Its generation number."""
        with self._cv:
            self._gen += 1
            self._job, self._spot = {**job, "gen": self._gen}, None
            return self._gen

    def aim(self, x: float, y: float, seq: int):
        """The pointer's newest spot (picture px), numbered: replaces one still waiting."""
        with self._cv:
            self._spot = (x, y, seq)
            self._cv.notify()

    def stop(self):
        with self._cv:
            self._gen += 1
            self._job, self._spot = None, None

    def close(self):
        with self._cv:
            self._closed = True
            self._cv.notify()

    def _run(self):
        while True:
            with self._cv:
                while not self._closed and (self._spot is None or self._job is None):
                    self._cv.wait()
                if self._closed:
                    return
                job, spot, self._spot = self._job, self._spot, None
            try:
                out = solve(job, *spot)
            except Exception as e:  # noqa: BLE001  handed back: the screen says it (fail loudly)
                out = {"error": str(e), "seq": spot[2]}
            out["gen"] = job["gen"]
            self._done(out)


def solve(job: dict, x: float, y: float, seq: int) -> dict:
    """One spot of a drag: the turns, the live payload, the overlay and the chip, with each part's time (ms)."""
    t0 = time.perf_counter()
    c = job["clay"]
    to = aim.point(aim.invert(job["world"]), G._on_plane(job["view"], x, y, job["point"]))
    stack = job.get("stack", ())                    # the animation layers: solved from the pose as shown
    turns = L.solve(c, job["bone"], job["local"], to, job["held"], job["t"], stack)
    t1 = time.perf_counter()
    pose = L.chain_pose(c, turns, job["t"], stack) if job["live"] else None
    t2 = time.perf_counter()
    drawn = PV.overlay(c, job["holds"], job["world"], job["view"], job["t"], job["w"], job["h"], set(turns), turns)
    chip = PV.chip(PV.chain_of(c), job["bone"], turns)
    t3 = time.perf_counter()
    return {"seq": seq, "turns": turns, "pose": pose, "drawn": drawn, "chip": chip,
            "calls": L.key_calls(turns, job["t"], c, job.get("layer", ""), stack),
            "ms": {"ik": (t1 - t0) * 1000, "pose": (t2 - t1) * 1000, "overlay": (t3 - t2) * 1000,
                   "solve": (t3 - t0) * 1000}}
