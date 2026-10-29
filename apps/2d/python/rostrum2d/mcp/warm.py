"""The looks' one held engine: look_frame, sheets, run_script's look, look_at and the review draw through one engine
process kept between calls, holding the scene. A look after an edit sends the engine only the nodes the edit made
(scene_keep.Keeper + scene_change: the screen's own path), so a single frame costs the frame, not a process start and a
whole scene load (5-10 s on a 70 s film before; ~1 s now).

The scene held is the whole composition (span 0..its end), whatever the call draws: the same description every
look, so the keeper reuses it. Paint pictures not made yet are made first, side by side, as describe does. Exports
start their own engine (a job that runs while the agent keeps looking).

One lock: one look draws at a time (a sheet's job and a quick look_frame never mix their frames in one engine). An
engine that died restarts itself on the next request (engine.py); the process ends with the server (atexit).
"""
from __future__ import annotations

import atexit
import math
import os
import threading
from contextlib import contextmanager

from rostrum_core import markers as M

from rostrum2d import drawing, write_on
from rostrum2d import scene as scene_mod
from rostrum2d.scene_keep import Keeper

_lock = threading.RLock()
_engine = None
_keeper = Keeper()


def scene(doc, comp_id: str, duration: float, times: list[float] | None = None) -> dict:
    """The composition's whole description as it is now, made again only where the document changed since the last look.
    `times`: the only moments the call draws: Drawn so far pictures are made for those frames (and a motion blur's
    reach), the others stand in until a look draws them (then only the drawings whose pictures were made are described
    again: scene_keep's `ran`; a repeat look at made moments reuses the whole description). The auto layout is solved
    for those frames too (layoutbake), so the description is exact only there: it is never exported (exports describe
    on their own)."""
    with _lock:
        args = (doc.data, comp_id, M.times(doc.folder), doc.folder, (0.0, duration))
        jobs: list = []
        drawn = None if times is None else _frames(doc.data, comp_id, times)
        got = _keeper.describe(*args, later=jobs, drawn=drawn)
        if jobs and drawn is not None:
            jobs = write_on.wanted(jobs, _frames(doc.data, comp_id, times, between=False))
        if jobs:
            drawing.make_all(jobs, None, None)      # paint pictures first (kept by content), then described with them
            _keeper.ran(jobs)
            got = _keeper.describe(*args, later=[], drawn=drawn)
        if got.get("warnings"):                     # a placeholder (a 3D render not made yet) may be ready next time
            _keeper.forget()
        return got


def _frames(data: dict, comp_id: str, times: list[float], between: bool = True) -> set:
    """The frame numbers drawing `times` reads: each time's frame and the motion blur's reach round it (scene._spare);
    `between`: also the frame after each, and one more either side (a key's value at a time between two frames is
    read from both: the auto layout's keys, layoutbake). A Drawn so far picture is its frame's alone (drawing.frame_number):
    a look at one moment of a painted piece made 3-4 pictures of each drawing where it shows one (Night Market's new
    moment: ~1.5 s -> ~0.5 s)."""
    comp = next((c for c in data.get("comps", []) if c["id"] == comp_id), {})
    fps, spare = comp.get("fps", 30), scene_mod._spare(comp, data)
    if not between:
        return {drawing.frame_number(t, fps) + k for t in times for k in range(-spare, spare + 1)}
    return {n + k for t in times for n in {math.floor(t * fps + 1e-6), round(t * fps)} for k in range(-spare - 1, spare + 2)}


@contextmanager
def engine(loaded: dict):
    """The held engine with `loaded` in it (only the change goes when it shares nodes with the scene held)."""
    global _engine
    from rostrum2d.engine import Engine
    with _lock:
        if _engine is None or _engine._stopped is not None:
            _engine = Engine()
        try:
            _engine.load(loaded)
        except Exception:
            _keeper.forget()                        # a refused scene: describe it whole next time
            raise
        yield _engine


_PREWARM = '''
comp("warm", width=320, height=180, duration=1, fps=30, background="#204060")
shape("box", w=120, h=60, fill="#ff7a59", x=100, y=90, radius=12, stroke=True, strokeColor="#ffffff", strokeWidth=3)
shape("dot", shape="ellipse", w=50, h=50, fill="#7ad0ff", x=240, y=90)
text("word", body="Warm", size=40, weight=700, color="#ffffff", x=160, y=40)
d = drawing("ink", w=96, h=64)
d.frame(0).paint("ink_p").stroke([(8, 8), (48, Y), (88, 40)], color="#ffffff", size=10, brush="bristle")
d.key("drawnSoFar", {0: 0, 1: 1})
'''


def prewarm() -> threading.Thread:
    """Readies the looks' engine in the background when the server starts: the process, its graphics card context, fonts
    and shaders, one small frame drawn (with a painted stroke half drawn: the painting kit made ready too), and the look's
    own checks run once on it, so an agent's first look costs its
    scene, not a cold start (a fresh session's first look: ~1-1.5 s more, before). A look that comes first waits for it
    (one lock), as it would have waited for its own start; a failure here is the next look's to say (it starts again)."""
    def run():
        import tempfile
        from pathlib import Path
        from rostrum_core import Document
        from rostrum2d import KIND, run_source
        from . import edge_cut, look_wash
        try:
            d = Document.new(KIND)
            # a stroke of its own each time: the painting kit makes a Drawn so far picture (the cache would only read one)
            d.run_script("warm.py", run_source(_PREWARM.replace("Y", str(20 + os.getpid() % 40)), "warm.py"))
            comp = d.data["comps"][0]
            with engine(scene_mod.describe(d.data, None, None, None, (0.0, 1.0), frames=[15])) as eng, tempfile.TemporaryDirectory(prefix="rostrum_warm_") as tmp:
                eng.still(0.5, Path(tmp) / "warm.png")
            edge_cut.warnings_at(d.data, comp, 0.5)
            look_wash.facts(comp, 0.5)
        except Exception:   # noqa: BLE001  (the first look starts the engine itself and says what failed)
            pass
    t = threading.Thread(target=run, name="looks-prewarm", daemon=True)
    t.start()
    return t


def forget():
    """Inputs outside the document changed (a 3D render finished): the next look describes and sends everything."""
    with _lock:
        _keeper.forget()


@atexit.register
def close():
    global _engine
    with _lock:
        if _engine is not None:
            _engine.close()
            _engine = None
