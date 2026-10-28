"""Where a shot's simulation stands, for the timeline's Simulate row, sim.status and the render paths.

    none          nothing in the shot Falls or is Cloth
    not computed  no stored result for these inputs, and none older to show
    stored        the result for the inputs as they are now is in the cache
    out of date   an input changed: the older result (the shot's simKey) is still shown, never rendered

A result made for the inputs as they are is "stored" whether or not the shot's simKey names it yet (a render path computed
it, or moving the bowl back brought the old inputs back); a simKey whose entry the cache dropped reads "not computed".
"""
from __future__ import annotations

from rostrum_core.cache import CACHE

from . import fields as SF
from .inputs import KIND, MOVING, bodies, cloths, falling, nested, sim_inputs, value


def _shot(data: dict, shot_id: str) -> dict:
    from ..compile import _shot
    return _shot(data, shot_id)


def count(req: dict, scene: dict) -> int:
    """How many things move: a copies item counts each copy, a cloth counts one."""
    nodes = {n["id"]: n for n in scene["items"]}
    n = 0
    for b in falling(req):
        node = nodes.get(b["item"], {})
        n += int(node.get("props", {}).get("count", 1)) if node.get("type") == "copies" else 1
    return n + len(cloths(req))


def state(data: dict, shot_id: str, folder=None, scene: dict | None = None) -> dict:
    """{"bodies", "falling", "cloth", "state", "frames", "key", "storedKey", "line", "inside"}: `key` the inputs' key now,
    `storedKey` the shot's simKey, `inside` the items set to simulate that can't (inside a group …); `falling` the things
    that fall (each copy counts; what Turn into keys can key), `cloth` the cloths (never keys)."""
    from ..compile import describe, shot_info
    shot, info = _shot(data, shot_id), shot_info(data, shot_id)
    name, frames, inside = shot.get("name") or shot_id, info["end"] - info["start"] + 1, nested(data)
    stored_key = shot.get(SF.KEY, "")
    if not any(value(b, "simulate") in MOVING for b in bodies(data)):
        return {"bodies": 0, "falling": 0, "cloth": 0, "state": "none", "frames": frames, "key": "", "storedKey": stored_key, "inside": inside,
                "line": f"{name}: nothing falls (Simulate › Falls or Cloth on an item)"}
    scene = scene if scene is not None else describe(data, shot_id, folder, sim="none")
    req, key = sim_inputs(data, shot_id, folder, scene)
    n = count(req, scene)
    if CACHE.get(KIND, key):
        st, words = "stored", "stored · up to date"
    elif stored_key and CACHE.get(KIND, stored_key):
        st, words = "out of date", "out of date · Simulate"
    else:
        st, words = "not computed", "not computed · Simulate"
    return {"bodies": n, "falling": n - len(cloths(req)), "cloth": len(cloths(req)), "state": st, "frames": frames, "key": key, "storedKey": stored_key, "inside": inside,
            "line": f"{name}: {n} {'body' if n == 1 else 'bodies'} · {words}"}


def adoptable(st: dict) -> bool:
    """A result for the inputs as they are is stored but the shot's simKey names an older one (or none): a render path
    computed it. Recording it (sim.run: the result is in the cache, nothing is computed) makes it the shot's stored result,
    so the row says Stored and the viewport shows the fall the render used."""
    return st.get("state") == "stored" and bool(st.get("key")) and st.get("key") != st.get("storedKey")
