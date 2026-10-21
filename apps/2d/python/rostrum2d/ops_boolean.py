"""`path.boolean`: union, subtract, intersect or exclude two or more path / shape layers into one new path layer,
with Skia's PathOps (skia-pathops, BSD-3-Clause), which keeps curves as curves.

Each input is first placed as the stage draws it (its x, y, anchor, scale, rotation), in the parent's px; the
result's box hugs the result, so it sits exactly where the inputs were. The inputs are removed (one undo step brings
them back): a hidden copy would still be drawn work, keyed and edited by mistake, and Rostrum has no "hidden" switch.
The result takes the first input's look (fill and stroke) and its place in the stack is the lowest input's.
"""
from __future__ import annotations

import pathops

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from . import pathdata as PD
from .kind import REGISTRY as R
from .ops_items import ID, new_item
from .ops_path import _LOOK, to_parent

MODES = {"union": pathops.PathOp.UNION, "subtract": pathops.PathOp.DIFFERENCE,
         "intersect": pathops.PathOp.INTERSECTION, "exclude": pathops.PathOp.XOR}


def outline(item: dict) -> str:
    """The filled area of a path or shape layer, as path data in its own box."""
    if item["type"] == "path":
        return item["d"]
    return PD.ellipse(item["w"], item["h"]) if item["shape"] == "ellipse" else PD.rect(item["w"], item["h"], item["radius"])


def skia_path(cmds, evenodd: bool) -> pathops.Path:
    p = pathops.Path()
    p.fillType = pathops.FillType.EVEN_ODD if evenodd else pathops.FillType.WINDING
    for c in cmds:
        if c[0] == "M":
            p.moveTo(*c[1:])
        elif c[0] == "L":
            p.lineTo(*c[1:])
        elif c[0] == "C":
            p.cubicTo(*c[1:])
        else:
            p.close()
    return p


def commands_of(p: pathops.Path) -> list[tuple]:
    out, cur = [], (0.0, 0.0)
    for verb, pts in p:
        if verb == pathops.PathVerb.MOVE:
            out.append(("M", *pts[0]))
        elif verb == pathops.PathVerb.LINE:
            out.append(("L", *pts[0]))
        elif verb == pathops.PathVerb.CUBIC:
            out.append(("C", *pts[0], *pts[1], *pts[2]))
        elif verb == pathops.PathVerb.QUAD:              # a quadratic as the same curve in cubic form
            (qx, qy), (x, y) = pts
            out.append(("C", cur[0] + 2 / 3 * (qx - cur[0]), cur[1] + 2 / 3 * (qy - cur[1]),
                        x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y), x, y))
        elif verb == pathops.PathVerb.CLOSE:
            out.append(("Z",))
            continue
        else:
            raise ValueError(f"PathOps gave a {verb} segment, which path data can't hold")
        cur = out[-1][-2:]
    return out


@R.operation("path.boolean", "Combine two or more path or shape layers into one new path: union, subtract (the "
             "first minus the others), intersect or exclude. They must be in the same group or composition. The "
             "inputs are removed; the new path sits where they were, with the first one's fill and stroke.",
             target=("path", "shape"), label="Combine",
             params=[Param.choice("mode", list(MODES), label="Mode", required=True), ID])
def path_boolean(ctx, targets, args):
    if len(targets) < 2:
        ctx.fail(codes.BAD_ARGUMENT, f"target {targets}", "a boolean needs two or more layers")
    idx = index(ctx.doc, ctx.kind.lists)
    parents = {idx[t].parent for t in targets}
    if len(parents) > 1:
        ctx.fail(codes.BAD_ARGUMENT, f"target {targets}", f"are in different groups ({', '.join(sorted(parents))}); "
                 "move them into one first (layer.arrange)")
    items = [ctx.item(t) for t in targets]
    result = None
    try:
        for it in items:
            cmds = PD.transformed(PD.commands(outline(it)), to_parent(it))
            p = skia_path(cmds, it.get("fillRule") == "evenodd")
            result = p if result is None else pathops.op(result, p, MODES[args["mode"]])
        cmds = commands_of(result)
    except (ValueError, pathops.PathOpsError) as e:
        ctx.fail(codes.BAD_ARGUMENT, f"target {targets}", f"can't be combined: {e}")
    if not cmds:
        ctx.fail(codes.BAD_ARGUMENT, f"target {targets}", f"{args['mode']} leaves nothing")
    first, parent, key = items[0], idx[targets[0]].parent, idx[targets[0]].key
    place = min(idx[t].index for t in targets)
    moved, (x0, y0, w, h) = PD.fit(cmds)
    item = new_item(ctx, "path", args)
    item.update({k: first[k] for k in _LOOK if k in first})
    item.update(d=PD.write(moved), w=w, h=h, x=x0 + w / 2, y=y0 + h / 2, fillRule="nonzero")
    for t in targets:
        ctx.remove(t)
    ctx.insert(parent, key, item, place)
