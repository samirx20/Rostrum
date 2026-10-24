"""Select first, then act: `layer.align`, `layer.distribute`, `layer.match_size`. They move or size the selected layers
inside their one parent (a composition or a group, in its px). Positions are changed the way `value.set` does it: a
still field changes, an animated field gets a key at `at` (own seconds, the same `at` as value.set; needed then)."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from . import boxes, fields as F
from .evaluate import resolve
from .kind import REGISTRY as R

PLACED = F.PLACED
SIZED = tuple(t for t in PLACED if t != "text")
AT = Param.number("at", label="At", min=0, max=36000, unit=" s", importance="deep",
                  help="The time (own seconds) to measure at and, for an animated field, to put the key at; 0 when left out")
EDGES = {"left": ("x", 0), "hcenter": ("x", 1), "right": ("x", 2), "top": ("y", 0), "vcenter": ("y", 1), "bottom": ("y", 2)}


def _put(ctx, id_, prop, value, args):
    R.get("value.set").fn(ctx, [id_], {"prop": prop, "v": round(value, 4), **({"at": args["at"]} if "at" in args else {})})


def _parent(ctx, targets):
    """The targets' one parent (they must share it, and it must not place them itself)."""
    idx = index(ctx.doc, ctx.kind.lists)
    parents = {idx[t].parent for t in targets}
    if len(parents) > 1:
        ctx.fail(codes.BAD_ARGUMENT, f"target {targets}", "are in different groups", hint="Move them into one first (layer.arrange).")
    parent = ctx.item(parents.pop())
    if parent["type"] == "group" and parent.get("layout", "none") != "none":
        ctx.fail(codes.BAD_ARGUMENT, f'target "{targets[0]}"', f"is placed by {parent['id']}'s auto layout")
    return parent


def _frame(parent: dict, t: float, pinned: bool = False):
    """The parent's own box as x0, y0, x1, y1: for a scene, the frame where it is at t (its centre and its size seen at
    its zoom, in world px; a pinned layer's own px are the frame's: 0, 0, width, height); a group's w x h."""
    if parent["type"] == "comp":
        w, h = float(parent.get("width", 1920)), float(parent.get("height", 1080))
        from .frame import view
        cam = None if pinned else view.shot(parent, t)
        if cam is None:
            return 0.0, 0.0, w, h
        z = cam.zoom or 1.0
        return cam.x - w / z / 2, cam.y - h / z / 2, cam.x + w / z / 2, cam.y + h / z / 2
    p = resolve(parent, t)
    return 0.0, 0.0, p["w"], p["h"]


def _span(box, axis):
    return (box[0], box[2]) if axis == "x" else (box[1], box[3])


@R.operation("layer.align", "Line layers up: `edge` left, hcenter, right, top, vcenter or bottom. `to` selection (the "
             "selection's combined box; the default for several layers) or composition (the frame, or the group's box for "
             "layers inside a group; the default for one layer). Layers keep their size and only move.",
             target=PLACED, label="Align",
             params=[Param.choice("edge", list(EDGES), label="Edge", required=True,
                                  labels={"hcenter": "Centre across", "vcenter": "Centre up and down"}),
                     Param.choice("to", ["selection", "composition"], label="To"), AT])
def layer_align(ctx, targets, args):
    parent, t = _parent(ctx, targets), args.get("at", 0.0)
    to = args.get("to", "selection" if len(targets) > 1 else "composition")
    if to == "selection" and len(targets) < 2:
        ctx.fail(codes.BAD_ARGUMENT, '"to"', "selection needs two or more layers", hint='Use to: "composition" for one layer.')
    items = {i: ctx.item(i) for i in targets}
    bx = {i: boxes.box(it, t) for i, it in items.items()}
    axis, how = EDGES[args["edge"]]
    if to == "composition":
        lo, hi = _span(_frame(parent, t, bool(items[targets[0]].get("screenLock"))), axis)
    else:
        lo, hi = min(_span(b, axis)[0] for b in bx.values()), max(_span(b, axis)[1] for b in bx.values())
    goal = (lo, (lo + hi) / 2, hi)[how]
    for i, b in bx.items():
        a, z = _span(b, axis)
        d = goal - (a, (a + z) / 2, z)[how]
        if abs(d) > 1e-9:
            _put(ctx, i, axis, resolve(items[i], t)[axis] + d, args)


@R.operation("layer.distribute", "Space three or more layers evenly along `axis` x (across) or y (up and down): the two "
             "outermost stay, the gaps between the layers become equal.", target=PLACED, label="Distribute",
             params=[Param.choice("axis", ["x", "y"], label="Along", required=True), AT])
def layer_distribute(ctx, targets, args):
    if len(targets) < 3:
        ctx.fail(codes.BAD_ARGUMENT, f"target {targets}", "distributing needs three or more layers")
    _parent(ctx, targets)
    t, axis = args.get("at", 0.0), args["axis"]
    rows = sorted((_span(boxes.box(ctx.item(i), t), axis), i) for i in targets)
    gap = ((rows[-1][0][1] - rows[0][0][0]) - sum(z - a for (a, z), _ in rows)) / (len(rows) - 1)
    cursor = rows[0][0][1] + gap
    for (a, z), i in rows[1:-1]:
        if abs(cursor - a) > 1e-9:
            _put(ctx, i, axis, resolve(ctx.item(i), t)[axis] + cursor - a, args)
        cursor += (z - a) + gap


@R.operation("layer.match_size", "Give layers the same size as another layer (`to`): its width, height or both, as it shows "
             "(its scale counted). Text has no width and height of its own and is refused.", target=SIZED, label="Match size",
             params=[Param.id("to", kind="layer", label="Same size as", required=True),
                     Param.choice("dims", ["both", "w", "h"], label="Match", default="both",
                                  labels={"both": "Width and height", "w": "Width", "h": "Height"}), AT])
def layer_match_size(ctx, targets, args):
    ref, t = ctx.item(args["to"]), args.get("at", 0.0)
    if ref["type"] not in SIZED:
        ctx.fail(codes.BAD_ARGUMENT, f'to "{ref["id"]}"', f"is a {ref['type']}, which has no size of its own")
    rp = resolve(ref, t)
    shown = {"w": rp["w"] * rp["scale"] * rp["scaleX"], "h": rp["h"] * rp["scale"] * rp["scaleY"]}
    for dim in ("w", "h") if args.get("dims", "both") == "both" else (args["dims"],):
        for i in targets:
            p = resolve(ctx.item(i), t)
            k = p["scale"] * p["scaleX" if dim == "w" else "scaleY"]
            if not k:
                ctx.fail(codes.BAD_ARGUMENT, f'target "{i}"', "is scaled to nothing")
            _put(ctx, i, dim, shown[dim] / k, args)
