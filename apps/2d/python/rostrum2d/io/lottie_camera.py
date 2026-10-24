"""The frame's move in a Lottie file. Lottie has no camera like ours, so the move is baked into the file and the
picture stays the preview's: one invisible null layer per depth does what the frame does to layers at that depth
(the engine's maths, frame/view.py `parts`; a frame riding a path where follow.ride puts it), with a keyframe every
frame, and each of the composition's own layers is parented to its depth's null. A layer riding a path is baked the
same way (`ride_keys`: where follow.ride puts it, a keyframe every frame). A layer pinned to the frame gets none;
layers inside a group follow their group. A frame that never leaves home writes nothing (the file is as before).

A cut (the frame's hold key) is a hold keyframe, so a player drawing between frames never blends two shots.
"""
from __future__ import annotations

from rostrum_core.keys import track_value

from .. import fields as F
from ..frame import view
from .lottie_keys import LINEAR, emit
from .lottie_props import Ctx


def _at(node: dict, name: str, t: float):
    """A scene node's field at t (its keys when keyed, else its still value; a field left out is its default, as the
    engine reads it)."""
    keys = node.get("anim", {}).get(name)
    if keys:
        return track_value(sorted(keys, key=lambda k: k["t"]), t)
    return node["props"][name] if name in node["props"] else F.param(node["type"], name).default


def has_camera(comp: dict) -> bool:
    """The frame ever leaves home (view.leaves_home): only then are nulls written."""
    return view.leaves_home(view.of(comp), comp)


def _cuts(frame: dict, fps: float) -> set[int]:
    """The frames where the frame jumps: each key after a hold key on its move."""
    out = set()
    for prop in ("x", "y", "zoom", "rotation"):
        keys = sorted(frame.get("anim", {}).get(prop) or [], key=lambda k: k["t"])
        out |= {round(k1["t"] * fps + 0.4999) for k0, k1 in zip(keys, keys[1:]) if k0.get("ease") == "hold"}
    return out


def _track(values: list, cuts: set[int]) -> dict:
    """A Lottie property from one value per frame: still when it never changes, else a keyframe every frame (linear,
    a hold before a cut)."""
    if all(v == values[0] for v in values):
        return {"a": 0, "k": values[0]}
    steps = [{"t": float(f), "v": v, "seg": None if f == len(values) - 1 else "hold" if f + 1 in cuts else LINEAR}
             for f, v in enumerate(values)]
    return {"a": 1, "k": emit(steps, lambda v: v)}


def ride_keys(node: dict, ctx: Ctx) -> dict:
    """A rider's position and turn (`ks` "p", "r"), a keyframe every frame where follow.ride puts it on its path, the
    camera's ride; a frame where the path is gone keeps the layer's own X, Y and rotation (as the engine draws it)."""
    from ..follow import ride      # follow imports the field tables, which import this package
    frames = round(ctx.duration * ctx.fps)
    own = ("x", "y", "rotation")
    got = [ride(node, ctx.siblings, f / ctx.fps, _at) or {k: _at(node, k, f / ctx.fps) for k in own}
           for f in range(frames + 1)]
    ctx.bake(f'riding the path "{node["props"].get("ridePath", "")}": a keyframe every frame')
    return {"p": _track([[round(g["x"], 4), round(g["y"], 4), 0] for g in got], set()),
            "r": _track([round(g["rotation"], 4) for g in got], set())}


def _null(name: str, ks: dict, frames: int) -> dict:
    return {"ddd": 0, "ty": 3, "nm": name, "sr": 1, "ks": ks, "ao": 0, "ip": 0, "op": frames, "st": 0, "bm": 0}


def bake(comp: dict, layers: list[dict], ctx: Ctx, first_ind: int) -> list[dict]:
    """Parent each of `layers` (the Lottie layers, `nm` = our layer id, `ind` set) to the null for its depth; returns
    the nulls, numbered from `first_ind`. Nothing when the frame never leaves home."""
    if not has_camera(comp):
        return []
    pr, nodes = comp["props"], {n["id"]: n for n in comp["layers"]}
    cx, cy, fps = pr["width"] / 2, pr["height"] / 2, float(pr["fps"])
    frames = round(pr["duration"] * fps)
    times = [f / fps for f in range(frames + 1)]
    frame = view.of(comp)
    cuts = _cuts(frame, fps)
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
            p = [view.parts((cx, cy), cam, d) for cam, d in zip(shots, depths)]
            ks = {"a": _track([[round(a, 4), round(b, 4), 0] for a, b, _, _ in p], cuts), "p": {"a": 0, "k": [cx, cy, 0]},
                  "s": _track([[round(z * 100, 4)] * 2 + [100] for _, _, z, _ in p], cuts),
                  "r": _track([round(r, 4) for *_, r in p], cuts), "o": {"a": 0, "k": 100}}
            null = _null(f"frame for {node['id']}" if keyed else f"frame at depth {key[1]:g}", ks, frames)
            null["ind"] = first_ind + len(nulls)
            nulls.append(null)
            by_key[key] = null["ind"]
        layer["parent"] = by_key[key]
    if nulls:
        ctx.layer = frame["id"]
        ctx.bake(f"the frame's move: carried by {len(nulls)} null parent layer(s) (Lottie has no 2D camera)")
    return nulls
