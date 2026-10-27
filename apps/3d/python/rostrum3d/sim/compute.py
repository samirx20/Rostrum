"""Computing a shot's simulation, once, into the shared cache, and `ready`: what every render path calls first.

    key = compute(doc.data, "drop03", folder, progress=lambda i, n, frame: …)     # blocking: a worker thread or a job
    scene = ready(doc.data, "drop03", folder, scene)                               # render paths: compute if needed

compute runs its own engine process (never the viewport's), sends the scene without any stored result laid over it,
asks the core's `simulate` with the cache entry's temporary folder, and writes `result.json` (the reply and the body
order) beside the core's `bodies.bin`. A failure leaves nothing in the cache and raises with the core's own words (which
thing, which frame, what to do).
"""
from __future__ import annotations

import json
from pathlib import Path

from rostrum_core.cache import CACHE

from .inputs import JOLT_VERSION, KIND, SIM_VERSION, falling, nested, sim_inputs
from .result import BIN, JSON, ROW


class SimError(RuntimeError):
    """The simulation could not be made (the core's words, or ours): which thing, which frame, what to do."""


class Cancelled(SimError):
    pass


def _engine_factory():
    from ..engine import Engine
    return Engine


def check(data: dict, req: dict):
    if inside := nested(data):
        raise SimError(f"{', '.join(inside)}: only things directly in the scene can fall or stay still, not inside a "
                       "group or copies; move it out first (item.arrange), or set Simulate: Off")
    if not falling(req):
        raise SimError("nothing in this shot falls: set Simulate › Falls on something first")


def _reply_checked(out: dict, req: dict, folder: Path) -> dict:
    if out.get("jolt") != JOLT_VERSION or out.get("sim") != SIM_VERSION:
        raise SimError(f"the 3D engine simulates with Jolt {out.get('jolt')} (sim {out.get('sim')}), this app expects "
                       f"Jolt {JOLT_VERSION} (sim {SIM_VERSION}): the engine and the app are from different builds")
    first, last = out["frames"]
    if (first, last) != (req["start"], req["end"]):
        raise SimError(f"the 3D engine simulated frames {first}–{last}, asked for {req['start']}–{req['end']}")
    f = folder / BIN
    want = (last - first + 1) * out["rows"] * ROW * 4
    if not f.is_file() or f.stat().st_size != want:
        raise SimError(f"the 3D engine said done but {f} is {f.stat().st_size if f.is_file() else 'missing'}, "
                       f"expected {want} bytes")
    return out


def compute(data: dict, shot_id: str, folder=None, engine_factory=None, progress=None, cancel=None) -> str:
    """The stored result's key for the shot as it is now, computing it first when the cache doesn't have it.
    `progress(done, total, frame)`; `cancel()` true stops it (its engine process ends; nothing is kept)."""
    from ..compile import describe
    scene = describe(data, shot_id, folder, sim="none")
    req, key = sim_inputs(data, shot_id, folder, scene)
    check(data, req)
    if CACHE.get(KIND, key):
        return key
    engine = (engine_factory or _engine_factory())()

    def frames(i, n, out):
        if cancel is not None and cancel():
            raise Cancelled("the simulation was stopped")
        if progress is not None:
            progress(i, n, out.get("frame"))

    def make(tmp: Path):
        engine.ensure_scene(scene)
        try:
            out = engine.simulate(progress=frames, **req, folder=str(tmp))
        except Cancelled:
            raise
        except Exception as e:  # noqa: BLE001  the core's words, unchanged
            raise SimError(str(e)) from e
        out = _reply_checked(out, req, tmp)
        (tmp / JSON).write_text(json.dumps({**out, "key": key, "shot": shot_id, "file": BIN}, indent=1), encoding="utf-8")

    try:
        CACHE.put(KIND, key, make, recipe={"shot": shot_id, "bodies": len(req["bodies"]), "frames": [req["start"], req["end"]]})
    finally:
        engine.close()
    return key


def needed(data: dict) -> bool:
    """Whether anything in the document Falls: every other render skips the simulation at no cost."""
    from .inputs import bodies, value
    return any(value(b, "simulate") == "falls" for b in bodies(data))


def ready(data: dict, shot_id: str, folder=None, scene: dict | None = None, engine_factory=None, progress=None,
          cancel=None) -> dict:
    """The scene a render draws: as given when nothing falls, else the stored result for the shot as it is now (computed
    first when it is not computed or out of date), compiled with sim="strict". So a stale result is never rendered.
    Blocking: call it from the render's own worker or job."""
    from ..compile import describe
    if not needed(data):
        return scene if scene is not None else describe(data, shot_id, folder, sim="none")
    compute(data, shot_id, folder, engine_factory, progress, cancel)
    return describe(data, shot_id, folder, sim="strict")


def ready_for_render(where: str, data: dict, shot_id: str, folder=None, scene: dict | None = None, engine_factory=None) -> dict:
    """`ready` for the render paths (render.still, render_video, sequence.sequence): a failure is the render's
    RENDER_FAILED, in the simulation's own words."""
    from rostrum_core.errors import RostrumError, codes
    try:
        return ready(data, shot_id, folder, scene, engine_factory)
    except SimError as e:
        raise RostrumError(codes.RENDER_FAILED, where, f'the simulation of shot "{shot_id}"', str(e),
                           hint="Nothing was rendered: a render never uses an out-of-date simulation.") from e
