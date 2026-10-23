"""A text that follows a path layer (`pathLayer`), and any layer that rides one (`ridePath`): the layer keeps only the
path layer's id; the engine resolves it on every frame (engine scene/follow.rs: the path's shape, box, transform and
trim window at that time). This module is the Python side of the same rule: `text.follow` and `layer.ride` (set the
reference, checked), `problem` (a reference that no longer resolves, said in words for inspect / look) and `taken`
(the values a following text or a rider shows at a time, for the approximate boxes in mcp/geometry.py). A layer and
its path sit side by side, in the same composition or group.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes

from . import fields as F, pathdata
from .evaluate import resolve, value_at
from .kind import LISTS, REGISTRY as R


def _target(layer: dict, siblings: list[dict], field: str = "pathLayer") -> tuple[dict | None, str]:
    """(the path layer `layer` names in `field`, "") or (None, what is wrong)."""
    want, op = layer.get(field, ""), ("text.follow" if field == "pathLayer" else "layer.ride")
    found = next((s for s in siblings if s["id"] == want), None)
    if found is None:
        return None, (f'{layer["id"]} follows the path layer "{want}", which is gone (deleted, or not in the same group): '
                      f'pick a path layer beside it ({op}) or clear {field}. Until then this composition can\'t be drawn.')
    if found["type"] != "path":
        return None, f'{layer["id"]} follows "{want}", which is a {found["type"]} layer, not a path'
    if field == "ridePath" and riding(found):
        return None, f'{layer["id"]} rides "{want}", which itself rides a path; a path that is ridden can\'t ride one'
    if field == "ridePath" and following(layer):
        return None, f'{layer["id"]} both follows a path layer (pathLayer) and rides one; clear one of them'
    return found, ""


def following(layer: dict) -> bool:
    return layer.get("type") == "text" and bool(layer.get("pathLayer"))


def riding(layer: dict) -> bool:
    return bool(layer.get("ridePath"))


def problem(layer: dict, siblings: list[dict]) -> str:
    """Why a following text's or a rider's path doesn't resolve ("" when it does, or it follows none)."""
    follow = _target(layer, siblings)[1] if following(layer) else ""
    return follow or (_target(layer, siblings, "ridePath")[1] if riding(layer) else "")


def problems(comp: dict) -> list[str]:
    """Every broken path reference in a composition, groups included."""
    out = []

    def walk(layers):
        for layer in layers:
            if msg := problem(layer, layers):
                out.append(msg)
            walk(layer.get("layers", []))
    walk(comp.get("layers", []))
    return out


def taken(layer: dict, siblings: list[dict], t: float) -> dict | None:
    """The values a following text takes from its path layer at time t (its transform fields, w, h), or a rider's
    place and turn on its path (x, y, rotation); None if neither."""
    if riding(layer):
        return ride(layer, siblings, t) if _target(layer, siblings, "ridePath")[0] else None
    path, _ = _target(layer, siblings) if following(layer) else (None, "")
    if path is None:
        return None
    p = resolve(path, t)
    return {**{f: p[f] for f in F.TAKEN}, "w": p["w"], "h": p["h"]}


def ride(layer: dict, siblings: list[dict], t: float, at=value_at) -> dict | None:
    """A rider's place and turn on its path at t (x, y, rotation), or None when it rides none (or the path is gone).
    `at(item, field, t)` reads a field: the document's layers by default; the Lottie export passes the scene's."""
    name = at(layer, "ridePath", t)
    path = next((s for s in siblings if s["id"] == name and s["type"] == "path"), None) if name else None
    if path is None:
        return None

    class Read:                                  # the fields at t, read when _ride asks for them
        def __init__(self, item):
            self.item = item

        def __getitem__(self, f):
            return at(self.item, f, t)
    own = Read(layer)
    on = _ride(Read(path), own["rideAt"], own["rideAlong"])
    if on is None:
        return None
    x, y, turn = on
    return {"x": own["x"] + x, "y": own["y"] + y, "rotation": own["rotation"] + (turn if own["rideTurn"] else 0.0)}


def _ride(p, at: str, along: float) -> tuple[float, float, float] | None:
    """Where a rider sits on a path layer with fields `p` (its parent's px) and the path's direction there (degrees),
    as engine scene/follow.rs `ride` says; measured here on the outline cut into short lines, for approximate boxes."""
    s, e = (min(max(p[f], 0.0), 1.0) for f in ("trimStart", "trimEnd"))
    frac = s if at == "start" else min(max(along, 0.0), 1.0) if at == "along" else max(e, s)
    hit = _along(p["d"], frac)
    if hit is None:
        return None
    (qx, qy), deg = hit
    r, sx, sy = math.radians(p["rotation"]), p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]

    def turn(vx, vy):
        return vx * sx * math.cos(r) - vy * sy * math.sin(r), vx * sx * math.sin(r) + vy * sy * math.cos(r)
    dx, dy = turn(qx - p["anchorX"] * p["w"], qy - p["anchorY"] * p["h"])
    tx, ty = turn(math.cos(math.radians(deg)), math.sin(math.radians(deg)))
    return p["x"] + dx, p["y"] + dy, math.degrees(math.atan2(ty, tx))


def _cubic(a, b, c, d, k):
    return (1 - k) ** 3 * a + 3 * (1 - k) ** 2 * k * b + 3 * (1 - k) * k * k * c + k ** 3 * d


def _along(d: str, frac: float):
    """((x, y), degrees) at `frac` of the whole length of `d` (subpath after subpath, as trim counts); None if no length."""
    runs: list[list[tuple[float, float]]] = []
    for c in pathdata.commands(d) if d else []:
        if c[0] == "M":
            runs.append([(c[1], c[2])])
        elif c[0] == "L":
            runs[-1].append((c[1], c[2]))
        elif c[0] == "C":
            x0, y0 = runs[-1][-1]
            runs[-1] += [(_cubic(x0, c[1], c[3], c[5], i / 24), _cubic(y0, c[2], c[4], c[6], i / 24)) for i in range(1, 25)]
        else:
            runs[-1].append(runs[-1][0])
    segs = [(a, b) for run in runs for a, b in zip(run, run[1:]) if math.dist(a, b) > 1e-9]
    if not segs:
        return None
    left = frac * sum(math.dist(a, b) for a, b in segs)
    for i, (a, b) in enumerate(segs):
        length = math.dist(a, b)
        if left <= length or i == len(segs) - 1:
            k = min(left / length, 1.0)
            return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k), math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        left -= length


def _parent_layers(ctx, id_: str) -> list[dict]:
    from rostrum_core.tree import index
    for entry in index(ctx.doc, ctx.kind.lists).values():
        layers = entry.item.get("layers") if "layers" in LISTS.get(entry.item.get("type"), []) else None
        if layers and any(l["id"] == id_ for l in layers):
            return layers
    return []


@R.operation("text.follow", "Make a text follow a path layer beside it (same composition or group): its letters sit on that "
             "path as the path is reshaped, moved, turned or drawn on (trim), on every frame. The text takes the path's place "
             "and turn; its own path data is cleared. path empty = stop following (the text keeps the path's place).",
             target="text", label="Follow path",
             params=[Param.text("path", label="Path layer", help="The id of a path layer in the same group; empty = stop following")])
def text_follow(ctx, targets, args):
    want = args.get("path", "")
    for t in targets:
        text, siblings = ctx.item(t), _parent_layers(ctx, t)
        if not want:
            if following(text) and (now := taken(text, siblings, 0.0)):
                for f in F.TAKEN:
                    ctx.set(t, f, now[f])
            ctx.set(t, "pathLayer", "")
            continue
        _, wrong = _target({**text, "pathLayer": want}, siblings)
        if wrong:
            ctx.fail(codes.BAD_ARGUMENT, f'path "{want}"', wrong.split(": pick")[0],
                     [s["id"] for s in siblings if s["type"] == "path"], hint="Give a path layer in the same group.")
        ctx.set(t, "path", "")
        ctx.set(t, "pathLayer", want)


@R.operation("layer.ride", "Make a layer or a camera ride a path layer beside it (same composition or group): on every frame its anchor (a camera: where it looks) "
             "sits on that path, at the tip of the part drawn on so far (Trim end, the default), at Trim start, or at a set "
             "place along it, as the path is reshaped, moved, turned or drawn on. Its X, Y become an offset from that point "
             "(set to 0 here); turn = it also turns with the path's direction. path empty = stop riding (the layer stays "
             "where it was at 0 s).",
             target=F.LAYERS, label="Ride path",
             params=[Param.text("path", label="Path layer", help="The id of a path layer in the same group; empty = stop riding"),
                     Param.choice("at", F.RIDE_AT, label="Rides at", default="end", labels=F.RIDE_AT_WORDS,
                                  help="end = the drawn-on tip, start = Trim start, along = the place `along` gives"),
                     Param.number("along", label="Along path", min=0, max=1, default=0.0,
                                  help="0 = the path's start, 1 = its end (used when at = along; key rideAlong to move along)"),
                     Param.toggle("turn", label="Turn with path", default=False, help="Also turn with the path's direction")])
def layer_ride(ctx, targets, args):
    want = args.get("path", "")
    for t in targets:
        layer, siblings = ctx.item(t), _parent_layers(ctx, t)
        if not want:
            if riding(layer) and (now := taken(layer, siblings, 0.0)):
                for f in ("x", "y", "rotation"):
                    ctx.set(t, f, now[f])
            ctx.set(t, "ridePath", "")
            continue
        if want == t or any(s.get("ridePath") == t for s in siblings):
            ctx.fail(codes.BAD_ARGUMENT, f'path "{want}"', f"{t} would ride itself, or is a path another layer rides; "
                     "a ridden path can't ride one")
        _, wrong = _target({**layer, "ridePath": want}, siblings, "ridePath")
        if wrong:
            ctx.fail(codes.BAD_ARGUMENT, f'path "{want}"', wrong.split(": pick")[0],
                     [s["id"] for s in siblings if s["type"] == "path"], hint="Give a path layer in the same group.")
        for f, v in (("ridePath", want), ("rideAt", args.get("at", "end")), ("rideAlong", float(args.get("along", 0.0))),
                     ("rideTurn", bool(args.get("turn", False))), ("x", 0.0), ("y", 0.0)):
            ctx.set(t, f, v)
