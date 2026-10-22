"""The 2D camera in a Lottie file. Lottie has no camera like ours, so its move is baked into the file and the picture
stays the preview's: one invisible null layer per depth does what the camera does to layers at that depth (the
engine's maths, camera/view.py `parts`), with a keyframe every frame, and each of the composition's own layers is
parented to its depth's null. A layer Locked to screen gets none; layers inside a group follow their group.

A cut from one camera to the next is a hold keyframe, so a player drawing between frames never blends two shots.
"""
from __future__ import annotations

from rostrum_core.keys import track_value

from ..camera import view
from .lottie_keys import LINEAR, emit
from .lottie_props import Ctx


def _at(node: dict, name: str, t: float):
    """A scene node's field at t (its keys when keyed, else its still value)."""
    keys = node.get("anim", {}).get(name)
    return track_value(sorted(keys, key=lambda k: k["t"]), t) if keys else node["props"][name]


def has_camera(comp: dict) -> bool:
    return any(n["type"] == "camera" for n in comp.get("layers", []))


def _track(values: list, cuts: set[int]) -> dict:
    """A Lottie property from one value per frame: still when it never changes, else a keyframe every frame (linear,
    a hold before a cut)."""
    if all(v == values[0] for v in values):
        return {"a": 0, "k": values[0]}
    steps = [{"t": float(f), "v": v, "seg": None if f == len(values) - 1 else "hold" if f + 1 in cuts else LINEAR}
             for f, v in enumerate(values)]
    return {"a": 1, "k": emit(steps, lambda v: v)}


def _null(name: str, ks: dict, frames: int) -> dict:
    return {"ddd": 0, "ty": 3, "nm": name, "sr": 1, "ks": ks, "ao": 0, "ip": 0, "op": frames, "st": 0, "bm": 0}


def bake(comp: dict, layers: list[dict], ctx: Ctx, first_ind: int) -> list[dict]:
    """Parent each of `layers` (the Lottie layers, `nm` = our layer id, `ind` set) to the null for its depth; returns
    the nulls, numbered from `first_ind`. Nothing when the composition has no camera."""
    if not has_camera(comp):
        return []
    pr, nodes = comp["props"], {n["id"]: n for n in comp["layers"]}
    cx, cy, fps = pr["width"] / 2, pr["height"] / 2, float(pr["fps"])
    frames = round(pr["duration"] * fps)
    times = [f / fps for f in range(frames + 1)]
    names = [n["id"] for n in comp["layers"] if n["type"] == "camera"]
    showing = [next((c for c in reversed(names) if _at(nodes[c], "start", t) <= t < _at(nodes[c], "end", t)), None)
               for t in times]
    cuts = {f for f in range(1, len(times)) if showing[f] != showing[f - 1]}
    shots = [view.shot(comp, t, _at) for t in times]
    nulls, by_key = [], {}
    for layer in layers:
        node = nodes[layer["nm"]]
        if node["props"].get("screenLock"):
            continue
        keyed = "depth" in node.get("anim", {})
        key = ("layer", node["id"]) if keyed else ("depth", node["props"].get("depth", 0.0))
        if key not in by_key:
            depths = [_at(node, "depth", t) for t in times] if keyed else [key[1]] * len(times)
            p = [view.parts(cx, cy, cam, d) for cam, d in zip(shots, depths)]
            ks = {"a": _track([[round(a, 4), round(b, 4), 0] for a, b, _, _ in p], cuts), "p": {"a": 0, "k": [cx, cy, 0]},
                  "s": _track([[round(z * 100, 4)] * 2 + [100] for _, _, z, _ in p], cuts),
                  "r": _track([round(r, 4) for *_, r in p], cuts), "o": {"a": 0, "k": 100}}
            null = _null(f"camera for {node['id']}" if keyed else f"camera at depth {key[1]:g}", ks, frames)
            null["ind"] = first_ind + len(nulls)
            nulls.append(null)
            by_key[key] = null["ind"]
        layer["parent"] = by_key[key]
    if nulls:
        ctx.layer = ", ".join(names)
        ctx.say(f"camera baked into {len(nulls)} null parent layer(s), a keyframe every frame (Lottie has no 2D camera); "
                "the picture matches the preview")
    return nulls
