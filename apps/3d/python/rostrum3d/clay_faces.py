"""Face shapes (PR4): a sculpt layer whose Amount is keyed (a smile coming on, a blink) changes the clay over time.

The core builds a clay from one list of steps; the clay store redoes only what changed between two lists (the layers
come after the Base, so a layer's Amount redoes that layer and the ones below it, never the Base: clay_layers.py).
So a moving Amount is a scene per distinct shape: the compiler works out each clay's steps for every frame where an
Amount moves (`variants`, one per distinct set of Amounts) and lays them beside the scene under KEY, which the core
never sees. `at(scene, frame)` is the scene to send for a frame (the same dict for the same shape, so a sender's
"already sent" check holds); `runs` splits a render's frames where the shape changes. The senders: the viewport's
worker (screen3d/frames.py) and the engine wrapper (engine.py: ensure_scene, view, render).
"""
from __future__ import annotations

from . import clay_layers

KEY = "clayFrames"          # beside a scene's items: {"start": frame, "clays": {clay id: {"perFrame", "variants"}}}
_MADE: dict = {}             # (id(scene), choice) -> (scene, its variant): the same dict for the same shape
_KEEP = 64


def per_frame(item: dict, fr) -> list[dict[str, float]] | None:
    """{layer id: Amount} at each frame of the shot, or None when no layer's Amount moves (one shape for the shot)."""
    if not any(lay.get("keys") for lay in clay_layers.layers(item)):
        return None
    out = [clay_layers.amounts(item, lambda i, f=f: fr.values(i, f)) for f in fr.frames]
    return out if any(a != out[0] for a in out) else None


def variants(amounts: list[dict[str, float]], built) -> dict:
    """{"perFrame": [variant per frame], "variants": [{"steps", "cache"}]}: `built(amount)` gives (steps, cache)."""
    index, out, per = {}, [], []
    for a in amounts:
        k = tuple(sorted(a.items()))
        if k not in index:
            index[k] = len(out)
            steps, cache = built(a)
            out.append({"steps": steps, "cache": cache})
        per.append(index[k])
    return {"perFrame": per, "variants": out}


def _choice(faces: dict, frame) -> tuple:
    k = 0 if frame is None else int(frame) - int(faces["start"])
    return tuple(c["perFrame"][min(max(k, 0), len(c["perFrame"]) - 1)] for c in faces["clays"].values())


def _swap(items: list, chosen: dict) -> list:
    out = []
    for n in items:
        if n.get("id") in chosen:
            n = {**n, **chosen[n["id"]]}
        elif n.get("children"):
            n = {**n, "children": _swap(n["children"], chosen)}
        out.append(n)
    return out


def at(scene: dict, frame=None) -> dict:
    """The scene to send for `frame` (None: the shot's first): itself when no Amount moves, else the variant with each
    face-shaped clay's steps for that frame, without KEY."""
    faces = scene.get(KEY) if isinstance(scene, dict) else None
    if not faces:
        return scene
    pick = _choice(faces, frame)
    hit = _MADE.get((id(scene), pick))
    if hit is not None and hit[0] is scene:
        return hit[1]
    chosen = {cid: c["variants"][i] for (cid, c), i in zip(faces["clays"].items(), pick)}
    out = {k: v for k, v in scene.items() if k != KEY}
    out["items"] = _swap(scene.get("items", []), chosen)
    if len(_MADE) >= _KEEP:
        _MADE.clear()
    _MADE[(id(scene), pick)] = (scene, out)
    return out


def runs(scene: dict, first: int, last: int) -> list[tuple[int, int]]:
    """Frames first..last cut where a face-shaped clay changes shape: [(a, b), …] (one run when nothing moves)."""
    faces = scene.get(KEY) if isinstance(scene, dict) else None
    if not faces or last <= first:
        return [(first, last)]
    out, a = [], first
    for f in range(first + 1, last + 1):
        if _choice(faces, f) != _choice(faces, f - 1):
            out.append((a, f - 1))
            a = f
    return out + [(a, last)]
