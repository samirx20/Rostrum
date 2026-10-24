"""Motion samples: where each moving layer is on screen, many times a second. The file RostrumSound's
`edit_sounds_from_motion` reads to place sounds on the picture's moves, landings, presses and steps (the 2D → Sound
hand-off; format in apps/2d/MOTION.md › Motion samples).

Read from the composition as it plays (layers timed from markers already in comp seconds, retime.py) through the one
geometry rule the look tools use (mcp/geometry.py flatten: parents, auto layout). Nothing is rendered.

A frame move is ONE event, not one per layer it carries: layers are sampled in the world's own place (without the
frame), and the frame, when it moves, is its own entry, `camera:<frame id>`: where the output's centre point of the
world lands in the export through it (it travels the way the picture travels), its zoom as scale. A cut (a hold key
on the frame) is one step of that entry.

Which layers: the ones that move on their own (their own x / y / scale / opacity change, or an auto layout moves them),
not the ones only carried by a moving group (the group itself is listed). Pass `only` to choose (camera:<id> too).
Outside its start / end a layer holds its nearest on-time place and has opacity 0, so a cut is one step, never a move.
"""
from __future__ import annotations

import math

from rostrum_core.errors import RostrumError, codes

from .frame import view as camera
from .evaluate import value_at
from .mcp.geometry import _apply, aabb, comp_size, flatten

FORMAT = "rostrum.motion-samples/1"
RATE = 60                      # samples a second (a move's speed curve needs more than the frame rate)
OWN = ("x", "y", "scale", "scaleX", "scaleY", "rotation", "opacity")


def _own(node: dict) -> tuple:
    p = node["props"]
    return tuple(round(float(p[k]), 4) for k in OWN)


def _screen(node: dict) -> tuple[float, float, float, float, float]:
    """(centre x, centre y, scale on screen, opacity, w, h of its box on screen)."""
    m, (x0, y0, x1, y1) = node["matrix"], aabb(node["corners"])
    scale = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
    seen = node["in_time"] or node["type"] == "camera"       # the frame is always seen: a cut is no step
    return (x0 + x1) / 2, (y0 + y1) / 2, scale, node["opacity"] if seen else 0.0, x1 - x0, y1 - y0


def _hold(values: list, on: list[bool]) -> list:
    """Off-time samples take the nearest on-time value (before it starts: its first place; after: its last)."""
    idx = [i for i, o in enumerate(on) if o]
    if not idx:
        return values
    out, j = list(values), 0
    for i in range(len(values)):
        while j + 1 < len(idx) and idx[j + 1] <= i:
            j += 1
        if not on[i]:
            out[i] = values[idx[j]] if idx[j] <= i else values[idx[0]]
    return out


def _cameras(comp: dict, times: list[float]) -> dict[str, list[dict]]:
    """camera:<id> -> per sample a node-like row (props, matrix, corners, opacity, in_time) for the scene's frame."""
    cams = [c for c in comp.get("layers", []) if c["type"] == "camera"]
    W, H = comp_size(comp)
    out = {}
    for c in cams:
        rows = []
        for t in times:
            p = {f: float(value_at(c, f, t)) for f in ("x", "y", "zoom", "rotation")}
            m = camera.layer_matrix(comp, camera.shot(comp, t), {"depth": 0.0})
            centre = _apply(m, W / 2, H / 2)
            rows.append({"type": "camera", "matrix": m, "in_time": True, "opacity": 1.0,
                         "corners": [(centre[0] - W / 2, centre[1] - H / 2), (centre[0] + W / 2, centre[1] + H / 2)],
                         "props": {"x": p["x"], "y": p["y"], "scale": p["zoom"], "scaleX": 1.0, "scaleY": 1.0, "rotation": p["rotation"],
                                   "opacity": 1.0}})
        out[f'camera:{c["id"]}'] = rows
    return out


def sample(comp: dict, rate: float = RATE, only: list[str] | None = None, where: str = "motion samples") -> dict:
    """The samples of a composition (as it plays). Fails loudly on an unknown id in `only`, or nothing to sample."""
    duration = float(comp.get("duration", 5.0))
    n = max(2, math.floor(duration * rate) + 1)
    times = [min(i / rate, duration - 1e-6) for i in range(n)]
    scene = {**comp, "layers": [x for x in comp.get("layers", []) if x["type"] != "camera"]}   # the scene's own place
    frames = [{nd["id"]: nd for nd in flatten(scene, t)} for t in times]
    for cid, rows in _cameras(comp, times).items():
        for f, row in zip(frames, rows):
            f[cid] = row
    ids = list(frames[0])
    if only:
        missing = [i for i in only if i not in frames[0]]
        if missing:
            raise RostrumError.not_found(where, "layer", missing[0], ids, "the layers of this composition")
        keep = list(only)
    else:
        keep = [i for i in ids if len({_own(f[i]) for f in frames if f[i]["in_time"]}) > 1]
    if not keep:
        raise RostrumError(codes.BAD_ARGUMENT, where, "the composition", "has no layer or camera that moves on its own",
                           hint="Name the layers to sample with `layers`.")
    layers = {}
    for lid in keep:
        rows = [_screen(f[lid]) for f in frames]
        on = [f[lid]["in_time"] for f in frames]
        x, y, s = (_hold([r[k] for r in rows], on) for k in range(3))
        seen = [r for r, o in zip(rows, on) if o] or rows
        layers[lid] = {"type": frames[0][lid]["type"], "x": [round(v, 2) for v in x], "y": [round(v, 2) for v in y],
                       "scale": [round(v, 4) for v in s], "opacity": [round(r[3], 4) for r in rows],
                       "w": round(max(r[4] for r in seen), 1), "h": round(max(r[5] for r in seen), 1)}
    width, height = comp_size(comp)
    return {"format": FORMAT, "comp": comp["id"], "rate": rate, "duration": duration, "width": width, "height": height,
            "layers": layers}
