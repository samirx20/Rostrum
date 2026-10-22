"""Vector path operations: points (the pen tool and agents use the same ones), fitting the box, shape → path, and
booleans (Skia's PathOps through skia-pathops, which keeps curves as curves).

Points are addressed by `i`, counted over all subpaths in order (pathdata.locate). Their x, y and handles are in
the layer's own px. Point edits never move the box: `path.fit` does that, keeping the drawing where it is.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from . import boxes, fields as F, pathdata as PD
from .kind import REGISTRY as R
from .ops_items import ID, new_item

N = lambda name, label, **kw: Param.number(name, label=label, min=-1e6, max=1e6, step=0.5, unit="px", **kw)  # noqa: E731
I = Param.number("i", label="Point", min=0, max=10**6, integer=True, required=True,
                 help="The point's number, counted over all subpaths from 0")
HANDLES = [N("inX", "In handle X", importance="secondary"), N("inY", "In handle Y", importance="secondary"),
           N("outX", "Out handle X", importance="secondary"), N("outY", "Out handle Y", importance="secondary")]


def _edit(ctx, t, fn):
    """Run fn(subs) on the path's points and write its d back. A morphing path (keys on d) is refused: its own d is
    ignored, so a point edit there would silently show nothing."""
    if any(k["prop"] == "d" for k in ctx.item(t).get("keys", [])):
        ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', "has shape keys on d (it morphs); change a shape with key.set on its key, or remove the keys first")
    subs = PD.to_points(ctx.item(t)["d"])
    fn(subs)
    ctx.set(t, "d", PD.from_points(subs))


def _handles(p, args, mirror=False):
    if "inX" in args or "inY" in args:
        p["in"] = [args.get("inX", p["in"][0]), args.get("inY", p["in"][1])]
        if mirror:
            p["out"] = [-p["in"][0], -p["in"][1]]
    if "outX" in args or "outY" in args:
        p["out"] = [args.get("outX", p["out"][0]), args.get("outY", p["out"][1])]
        if mirror:
            p["in"] = [-p["out"][0], -p["out"][1]]


@R.operation("path.add_point", "Add a point to a path (a corner, or a smooth point with handles). It goes after "
             "point `after`, or starts a new subpath with `new`, or ends the last subpath (a new one when that is closed).", target="path",
             label="Add point", params=[N("x", "X", required=True), N("y", "Y", required=True), *HANDLES,
                                        Param.number("after", label="After point", min=0, max=10**6, integer=True, importance="deep"),
                                        Param.toggle("new", label="New subpath", importance="deep")])
def point_add(ctx, targets, args):
    def add(subs):
        p = PD._pt(args["x"], args["y"])
        _handles(p, args)
        if args.get("new") or not subs or ("after" not in args and subs[-1]["closed"]):   # a closed shape is never extended
            subs.append({"closed": False, "points": [p]})
        elif "after" in args:
            s, k = _locate(ctx, subs, args["after"])
            subs[s]["points"].insert(k + 1, p)
        else:
            subs[-1]["points"].append(p)
        sub = next(s for s in subs if any(q is p for q in s["points"]))
        if p["out"] != [0, 0] and not sub["closed"] and sub["points"][-1] is p:
            # Path data holds an out handle only as the start of the next curve: kept silently it would be lost.
            ctx.fail(codes.BAD_ARGUMENT, "outX / outY", "can't be kept on the last point of an open path (path data "
                     "stores it only once a point follows); add the next point, then path.set_point this one's outX / outY")
    for t in targets:
        _edit(ctx, t, add)


@R.operation("path.set_point", "Move a path's point or its handles (offsets from the point). `mirror` keeps the "
             "two handles opposite (a smooth point).", target="path", label="Move point",
             params=[I, N("x", "X"), N("y", "Y"), *HANDLES, Param.toggle("mirror", label="Mirror handles", importance="secondary")])
def point_set(ctx, targets, args):
    def move(subs):
        s, k = _locate(ctx, subs, args["i"])
        p = subs[s]["points"][k]
        p["x"], p["y"] = args.get("x", p["x"]), args.get("y", p["y"])
        _handles(p, args, args.get("mirror", False))
    for t in targets:
        _edit(ctx, t, move)


@R.operation("path.remove_point", "Remove a point from a path (a subpath left empty goes too).", target="path",
             label="Remove point", importance="secondary", params=[I])
def point_remove(ctx, targets, args):
    def remove(subs):
        s, k = _locate(ctx, subs, args["i"])
        del subs[s]["points"][k]
        if not subs[s]["points"]:
            del subs[s]
    for t in targets:
        _edit(ctx, t, remove)


@R.operation("path.close", "Close (or open) the subpath that holds point `i` (the last subpath when left out).",
             target="path", label="Close path",
             params=[Param.number("i", label="Point", min=0, max=10**6, integer=True, importance="deep"),
                     Param.toggle("closed", label="Closed", default=True)])
def path_close(ctx, targets, args):
    def close(subs):
        s = _locate(ctx, subs, args["i"])[0] if "i" in args else len(subs) - 1
        if s < 0:
            ctx.fail(codes.BAD_ARGUMENT, "path", "has no points yet")
        subs[s]["closed"] = args.get("closed", True)
    for t in targets:
        _edit(ctx, t, close)


def _locate(ctx, subs, i):
    try:
        return PD.locate(subs, i)
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, f"i={i}", str(e))


def to_parent(item: dict):
    """local box px → the parent's px, as the stage draws the layer (contract § 4 Transform; tilt refused)."""
    if item.get("tiltX") or item.get("tiltY"):
        raise ValueError(f"{item['id']} is tilted (2.5D); a tilted layer can't be combined as a flat path")
    a, b, c, d, e, f = boxes.matrix(item, item["w"], item["h"])
    return lambda x, y: (a * x + c * y + e, b * x + d * y + f)


def _fit_fields(ctx, t, cmds, keep_place=True) -> dict:
    """d, w, h, x, y so the box hugs the curve and the drawing stays where it is."""
    item = ctx.item(t)
    moved, (x0, y0, w, h) = PD.fit(cmds)
    out = {"d": PD.write(moved), "w": w, "h": h}
    if keep_place:
        old = to_parent(item)
        new = to_parent({**item, "w": w, "h": h, "x": 0.0, "y": 0.0})
        ox, oy = old(x0, y0)
        nx, ny = new(0.0, 0.0)
        out.update(x=ox - nx, y=oy - ny)
    return out


@R.operation("path.fit", "Fit a path's box to its points; the drawing stays where it is (the anchor, gradients "
             "and the inspector's width use the box).", target="path", label="Fit box", importance="secondary")
def path_fit(ctx, targets, args):
    keyed = lambda it: {k["prop"] for k in it.get("keys", [])}  # noqa: E731
    for t in targets:
        if keyed(ctx.item(t)) & {"x", "y"}:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', "has keys on x or y; fitting would move them")
        try:
            fields = _fit_fields(ctx, t, PD.commands(ctx.item(t)["d"]))
        except ValueError as e:
            ctx.fail(codes.BAD_ARGUMENT, f"{t}.d", str(e))
        for k, v in fields.items():
            ctx.set(t, k, v)


def shape_d(item: dict) -> str:
    """A shape's outline as path data in its own box (its outline is drawn inside the box: inset by half its width,
    so a centred path stroke covers the same pixels)."""
    inset = item["strokeWidth"] / 2 if item.get("stroke") else 0.0
    if item["shape"] == "ellipse":
        return PD.ellipse(item["w"], item["h"], inset)
    return PD.rect(item["w"], item["h"], item.get("radius", 0.0), inset)


@R.operation("shape.to_path", "Turn rect / ellipse shapes into editable paths (same id, place, look, effects, "
             "masks and keys).", target="shape", label="Convert to path", importance="secondary")
def shape_to_path(ctx, targets, args):
    for t in targets:
        shape, loc = ctx.item(t), index(ctx.doc, ctx.kind.lists)[t]
        bad = {k["prop"] for k in shape.get("keys", [])} - set(F.animatable("path"))
        if bad:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f"has keys on {', '.join(sorted(bad))}, which a path "
                     "can't animate; remove them first")
        path = {**{k: v for k, v in shape.items() if k not in ("shape", "radius")}, **F.defaults("path"),
                **{k: shape[k] for k in ("fill", "stroke", "strokeColor", "strokeWidth", "w", "h", *_TRANSFORM)},
                "type": "path", "d": shape_d(shape), "cap": "butt", "join": "miter"}
        ctx.remove(t)
        ctx.insert(loc.parent, loc.key, path, loc.index)


_TRANSFORM = [p.name for p in F.TRANSFORM]
_LOOK = ("filled", "fill", "fillRule", "stroke", "strokeColor", "strokeWidth", "cap", "join", "miter", "dash", "gap")
from . import ops_boolean  # noqa: E402,F401  (path.boolean registers on REGISTRY)
