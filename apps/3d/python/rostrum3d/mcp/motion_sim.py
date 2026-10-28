"""look_motion's simulation: a shot's simulated things measured from its stored result, as the viewport shows them.

A thing set to Falls moves by the result, not by its keys: its x y z rx ry rz per frame of the shot (Timing and Simplify
applied, as overlay.py lays them over a compiled scene) replace its keyed ones in the Track. The result read is the one for
the scene as it is (stored), else the shot's older one (out of date: what the viewport keeps showing), else none (not
computed: the things are where their keys put them). Either of the last two is said in the reply, never an all-clear.
A cloth and a falling copies item are not measured here (their folds, each copy's fall): they are named as not measured.
"""
from __future__ import annotations

from rostrum_core.cache import CACHE

from ..sim.compute import needed
from ..sim.inputs import KIND, bodies, shot_value, value
from ..sim.result import read, stylized, trs
from ..sim import fields as SF
from ..sim.state import state


def moves(data: dict, info: dict, folder=None) -> dict | None:
    """None when nothing in the document is simulated; else {"state", "moves": {item: {prop: [value per shot frame]}},
    "skip": {item: why not measured}, "line": what the reply says about it}."""
    if not needed(data):
        return None
    from ..compile import _shot
    shot_id = info["id"]
    st = state(data, shot_id, folder)
    if st["state"] == "none":
        return None
    key = {"stored": st["key"], "out of date": st["storedKey"]}.get(st["state"], "")
    where = CACHE.get(KIND, key) if key else None
    out, skip = {}, {}
    falls = []
    for item in bodies(data):
        kind, id_ = value(item, "simulate"), item["id"]
        if kind == "cloth":
            skip[id_] = f"{id_} is cloth: its folds are simulated, not measured here (look_frame shows them)"
        elif kind == "falls" and item["type"] == "copies":
            skip[id_] = f"{id_}'s copies fall in the simulation; each copy's path is not measured here (look_frame what \"sheet\" shows them)"
        elif kind == "falls":
            falls.append(id_)
    if where is not None:
        res, shot = read(where), _shot(data, shot_id)
        step, simplify = SF.TIMINGS[shot_value(shot, "simTiming")], int(shot_value(shot, "simSimplify"))
        s0, s1 = info["start"], info["end"]
        for id_ in falls:
            if rows := res.rows_of(id_):
                out[id_] = trs(stylized(res, rows[0], range(s0, s1 + 1), s0, step, simplify))
    name, n = _shot(data, shot_id).get("name") or shot_id, len(falls)
    things = f"{n} falling thing{'' if n == 1 else 's'}"
    if st["state"] == "stored":
        line = f"Simulation: {things} measured from the stored result (up to date)." if n else None
    elif where is not None:
        line = (f"The simulation of shot \"{name}\" is OUT OF DATE (something it depends on changed): {things} measured from "
                "the older result the viewport still shows, not the fall the scene would make now. run_simulation, wait "
                "for it with inspect_job, then look again.")
    else:
        line = (f"The simulation of shot \"{name}\" is NOT COMPUTED: {things} measured at their keyed places, not where "
                "they will fall. run_simulation, wait for it with inspect_job, then look again.")
    return {"state": st["state"], "moves": out, "skip": skip, "line": line}
