"""What a shot's simulation is made of: its bodies, the core's `simulate` request (ENGINE_CONTRACT, brief 25 design §3)
and the key its stored result has in the shared cache (kind "sim").

The key is the content of everything that changes the result: each body's compiled node (its shape, its place and keys,
without what only changes its look: material, paint, which camera sees copies), its Simulation fields and its speed at the
first frame; every still body's node; the ground; the frames and the frame rate; and the engine (SIM_ENGINE, mirrored in the
core, which says its own in every reply). Timing and Simplify are not in it: they are applied when reading (result.py).

Falls from (fallStart, seconds into the shot): a falling body held still until then goes as "wakeFrame" (frames after the
shot's start), only when it is above 0, so every result made before it keeps its key.

Cloth (brief 26b): a shape set to Cloth goes as {"item", "kind": "cloth", "weight" (kg/m²), "stiffness" (0–1), "pinned",
"friction"}; its compiled node and these settings are in the key like any body's.
"""
from __future__ import annotations

import hashlib
import json

from rostrum_core.cache import cache_key

from . import fields as SF

SIM_VERSION = 3                                  # the core's `sim` in its reply; bump both together
JOLT_VERSION = "5.6.0"                           # third_party/jolt (the core's `jolt` in its reply)
SIM_ENGINE = f"rostrum3d-sim@{SIM_VERSION}+jolt@{JOLT_VERSION}"
KIND = "sim"                                     # the shared cache's kind
MOVING = ("falls", "cloth")                       # kinds that move (the rest only collide)
LOOK_ONLY = {"material", "seenBy", "seenSize", "frontMaterial", "bevelMaterial", "sideMaterial", "backMaterial"}
_DEFAULTS = {p.name: p.default for p in [*SF.ITEM, *SF.CLOTH_ITEM]}


def value(item: dict, name: str):
    """An item's Simulation field, its default when the document was made before brief 25."""
    return item.get(name, _DEFAULTS[name])


def shot_value(shot: dict, name: str):
    return shot.get(name, next(p.default for p in SF.SHOT if p.name == name))


def bodies(data: dict) -> list[dict]:
    """The top-level items that Fall or Stay still, in the scene's order."""
    return [i for i in data.get("items", []) if i.get("type") in SF.TYPES and value(i, "simulate") != "off"]


def nested(data: dict) -> list[str]:
    """Items set to simulate that sit inside a group, copies item or rig: only top-level items can be bodies."""
    out, stack = [], [c for i in data.get("items", []) for c in i.get("children", [])]
    while stack:
        it = stack.pop()
        if it.get("type") in SF.TYPES and value(it, "simulate") != "off":
            out.append(it["id"])
        stack += it.get("children", [])
    return sorted(out)


def _look_free(node):
    """A compiled node without what only changes its look (the result is the same whatever its colour)."""
    if isinstance(node, dict):
        return {k: _look_free(v) for k, v in node.items()
                if k not in LOOK_ONLY and not k.startswith("paint") and k not in ("sim", "cloth")}
    if isinstance(node, list):
        return [_look_free(v) for v in node]
    return node


def _velocity(node: dict, fps: float) -> list[float]:
    """Its speed at the first frame (metres a second) from its keyed position, so a thrown thing keeps flying."""
    anim = node.get("anim") or {}
    return [round((anim[k][1] - anim[k][0]) * fps, 6) if len(anim.get(k) or ()) > 1 else 0.0 for k in "xyz"]


def sim_inputs(data: dict, shot_id: str, folder=None, scene: dict | None = None) -> tuple[dict, str]:
    """(the core's `simulate` request without `folder` and `progress` (Engine.simulate adds it), the stored result's key). `scene`: compile.describe(...,
    sim="none") when the caller has it already (it is made here otherwise)."""
    from ..compile import _shot, describe, shot_info
    info, shot = shot_info(data, shot_id), _shot(data, shot_id)
    if scene is None:
        scene = describe(data, shot_id, folder, sim="none")
    nodes = {n["id"]: n for n in scene["items"]}
    ground = {"y": 0.0} if shot_value(shot, "simGround") else None
    reqs, recipe = [], []
    for item in bodies(data):
        kind, falls = value(item, "simulate"), value(item, "simulate") == "falls"
        if kind == "cloth":
            body = {"item": item["id"], "kind": "cloth", "weight": float(value(item, "clothWeight")),
                    "stiffness": float(value(item, "stiffness")), "pinned": value(item, "pinned"),
                    "friction": float(value(item, "friction"))}
            reqs.append(body)
            recipe.append({"body": body, "node": _look_free(nodes[item["id"]])})
            continue
        body = {"item": item["id"], "kind": kind,
                "mass": 0 if value(item, "massFromSize") else float(value(item, "mass")),
                "bounce": float(value(item, "bounce")), "friction": float(value(item, "friction")),
                "starts": value(item, "starts") if falls else "moving", "shape": value(item, "simShape"),
                "velocity": _velocity(nodes[item["id"]], info["fps"]) if falls else [0.0, 0.0, 0.0]}
        if not falls:
            body["mass"] = 0
        elif (wake := round(float(value(item, "fallStart")) * info["fps"])) > 0:   # sent only when set: older keys hold
            body["wakeFrame"] = min(wake, info["end"] - info["start"] + 1)
        reqs.append(body)
        recipe.append({"body": body, "node": _look_free(nodes[item["id"]])})
    req = {"start": info["start"], "end": info["end"], "fps": info["fps"], "ground": ground, "bodies": reqs}
    content = json.dumps({"bodies": recipe, "ground": ground}, sort_keys=True, separators=(",", ":"))
    key = cache_key(KIND, SIM_ENGINE, [hashlib.sha256(content.encode("utf-8")).hexdigest()],
                    {"start": info["start"], "end": info["end"], "fps": info["fps"]})
    return req, key


def falling(req: dict) -> list[dict]:
    return [b for b in req["bodies"] if b["kind"] == "falls"]


def cloths(req: dict) -> list[dict]:
    return [b for b in req["bodies"] if b["kind"] == "cloth"]


def moving(req: dict) -> list[dict]:
    """What the simulation moves: falling bodies and cloth."""
    return [b for b in req["bodies"] if b["kind"] in MOVING]
