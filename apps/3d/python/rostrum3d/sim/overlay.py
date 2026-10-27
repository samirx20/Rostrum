"""The stored result laid over a compiled scene (compile.describe's `sim`):

    "use"     the viewport, look tools: the result for the inputs as they are, else the shot's older one (out of date: the
              viewport keeps showing it), else nothing
    "none"    the scene the simulation itself starts from
    "strict"  renders: the result for the inputs as they are, or SimError (a stale result is never rendered; the render
              paths compute first: compute.ready)

A falling item gets `anim` x y z rx ry rz per frame of the shot (before the result's first frame it holds the first, after
its last the last); a falling copies item gets `sim` (the core reads its copies' places from the file itself). Timing and
Simplify, the shot's, are applied here (result.py). A cloth item (brief 26b) gets `cloth` {"file", "start", "end", "step",
"smooth"}: the core replaces its mesh's points and faces from the file per frame; its place is held at the shot's first
frame (the stored points are in its own space as it stood then), so keys on its x … sz no longer move it.
"""
from __future__ import annotations

from rostrum_core.cache import CACHE

from . import fields as SF
from .compute import SimError, needed
from .inputs import KIND, shot_value, sim_inputs
from .result import BIN, cloth_file, read, stylized, trs

PLACE = ("x", "y", "z", "rx", "ry", "rz", "sx", "sy", "sz")

MODES = ("use", "none", "strict")


def _entry(data: dict, shot_id: str, folder, scene: dict, mode: str):
    from ..compile import _shot
    req, key = sim_inputs(data, shot_id, folder, scene)
    if (now := CACHE.get(KIND, key)) is not None:
        return now, req
    if mode == "strict":
        older = _shot(data, shot_id).get(SF.KEY)
        why = "is out of date (something it depends on changed)" if older and CACHE.get(KIND, older) else "is not computed yet"
        raise SimError(f'shot "{shot_id}": its simulation {why}; simulate it first (the Simulate row, sim.run or the '
                       "run_simulation tool). A render never uses an out-of-date one")
    older = _shot(data, shot_id).get(SF.KEY)
    return (CACHE.get(KIND, older) if older else None), req


def apply(scene: dict, data: dict, shot_id: str, folder=None, mode: str = "use") -> dict:
    if mode not in MODES:
        raise ValueError(f'sim: "{mode}" is not one of {", ".join(MODES)}')
    if mode == "none" or not needed(data):
        return scene
    from ..compile import _shot
    folder_, req = _entry(data, shot_id, folder, scene, mode)
    if folder_ is None:
        return scene
    res = read(folder_)
    shot = _shot(data, shot_id)
    step, simplify = SF.TIMINGS[shot_value(shot, "simTiming")], int(shot_value(shot, "simSimplify"))
    s0, s1 = scene["shot"]["start"], scene["shot"]["end"]
    frames = range(s0, s1 + 1)
    nodes = {n["id"]: n for n in scene["items"]}
    for b in req["bodies"]:
        node = nodes.get(b["item"])
        if b["kind"] != "cloth" or node is None or not any(c["item"] == b["item"] for c in res.reply.get("cloth", [])):
            continue
        node["cloth"] = {"file": str(res.folder / cloth_file(b["item"])), "start": res.start, "end": res.end,
                         "step": step, "smooth": simplify}
        anim = node.get("anim") or {}
        for k in PLACE:
            if k in anim:
                node["props"][k] = anim.pop(k)[0]
    falls = {b["item"] for b in req["bodies"] if b["kind"] == "falls"}
    for item in sorted(falls & {b["item"] for b in res.bodies}):
        node, rows = nodes.get(item), res.rows_of(item)
        if node is None or not rows:
            continue
        if node["type"] == "copies":
            node["sim"] = {"file": str(res.folder / BIN), "row": rows[0], "rows": len(rows), "of": res.rows,
                           "start": res.start, "end": res.end, "step": step, "smooth": simplify}
            continue
        per = trs(stylized(res, rows[0], frames, s0, step, simplify))
        anim = node.setdefault("anim", {})
        for k, vals in per.items():
            node["props"][k] = vals[0]
            anim[k] = vals
    return scene
