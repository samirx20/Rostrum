"""Fog by distance (`frame.fog`): layers farther behind the frame fade toward a fog colour, so far layers read as far.
It is built from what a scene already has: a sheet of the fog colour, pinned to the frame (no parallax), laid just
above each depth layer, so the layers under it are veiled and the ones above are not. Each sheet's opacity is worked out
so the veil on a layer adds up to what its depth asks (`amount` at `far`, nothing at `near`, in between by `curve`). The
sheets are ordinary layers (ids `fog_<layer>`, named "Fog over ..."): key a sheet's opacity to let the fog roll in or
clear, recolour it, delete it. Running it again rebuilds them; `amount` 0 removes them. Depth of field still blurs
the layers; fog is what makes the blur read as air. Fog follows the stack, so layers must be ordered back to front;
a layer drawn above one that is farther away is refused, by name."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from .evaluate import value_at
from .kind import REGISTRY as R
from .ops_items import new_item

PREFIX = "fog_"
DEFAULT_FOG = "#9fb4c4"


def wanted(depth: float, near: float, far: float, amount: float, curve: float) -> float:
    """The share of fog colour a layer at `depth` should show: 0 at `near`, `amount` at `far` and beyond."""
    share = min(1.0, max(0.0, (depth - near) / (far - near)))
    return amount * share ** curve


def sheets(rows: list[tuple[str, float]], near: float, far: float, amount: float, curve: float):
    """([(layer id, sheet opacity)] top layer first, [ids foggier than the layer above them allows]) for `rows`
    ((id, depth), bottom of the stack first)."""
    out, clamped, above = [], [], 0.0               # above: the fog the sheets laid so far put over what is below them
    for id_, depth in reversed(rows):
        want = wanted(depth, near, far, amount, curve)
        if want + 1e-9 < above:
            clamped.append(id_)
            out.append((id_, 0.0))
            continue
        opacity = 1.0 - (1.0 - want) / (1.0 - above) if above < 1.0 else 0.0
        out.append((id_, round(opacity, 4)))
        above = 1.0 - (1.0 - above) * (1.0 - opacity)
    return out, clamped


@R.operation("frame.fog", "Fog by distance: layers farther behind the frame fade toward a fog colour. `amount` is how much fog "
             "colour a layer at depth `far` shows (0 removes the fog), nothing at `near`, growing by `curve` in between "
             "(1 steady, above 1 clear for longer). Built as fog-colour sheets pinned to the frame between the layers "
             "(`fog_<layer>`); key their opacity to roll the fog in, or recolour them. Run again to rebuild.",
             target="camera", label="Fog",
             params=[Param.color("color", label="Fog colour", default=DEFAULT_FOG),
                     Param.number("amount", label="Amount", default=0.6, min=0, max=1, step=0.05, display="percent"),
                     Param.number("near", label="Clear until depth", default=0.0, min=-0.99, max=1000),
                     Param.number("far", label="Full fog at depth", min=-0.99, max=1000,
                                  help="Default: the depth of the farthest layer"),
                     Param.number("curve", label="Curve", default=1.0, min=0.2, max=5, step=0.1, importance="secondary"),
                     Param.number("at", label="At", default=0.0, min=0, max=36000, unit="s",
                                  help="The moment whose depths are read (depths that are keyed)")])
def frame_fog(ctx, targets, args):
    for fid in targets:
        comp_id = ctx.idx[fid].parent
        comp = ctx.item(comp_id)
        for layer in [l for l in comp["layers"] if l["id"].startswith(PREFIX) and l.get("screenLock")]:
            ctx.remove(layer["id"])
        amount, t = args.get("amount", 0.6), args.get("at", 0.0)
        if amount <= 0:
            continue
        stack = [l for l in ctx.item(comp_id)["layers"] if l["type"] != "camera" and not l.get("screenLock")]
        if not stack:
            ctx.fail(codes.BAD_ARGUMENT, comp_id, "has no layers to put fog between",
                     hint="Add the layers first, with their depths (shape.set depth).")
        rows = [(l["id"], float(value_at(l, "depth", t))) for l in stack]
        near = args.get("near", 0.0)
        far = args.get("far", max(d for _, d in rows))
        if far <= near:
            ctx.fail(codes.BAD_ARGUMENT, "far", f"{far} is not beyond near {near}",
                     hint="Give `far` the depth where the fog is full; farther layers must have a bigger depth.")
        planned, clamped = sheets(rows, near, far, amount, args.get("curve", 1.0))
        if clamped:
            ctx.fail(codes.CONFLICT, ", ".join(clamped), "sit above a layer that is farther away, so fog cannot give them more than it",
                     hint="Fog follows the stack: order the layers back to front (the farthest lowest), or fix the depths.")
        w, h = comp.get("width", 1920.0), comp.get("height", 1080.0)
        for id_, opacity in planned:                # top layer first: laying one above a layer shifts none below it
            if opacity <= 0:
                continue
            name = ctx.item(id_).get("name") or id_
            sheet = new_item(ctx, "shape", {"id": PREFIX + id_, "name": f"Fog over {name}"})
            sheet.update({"w": w, "h": h, "x": w / 2, "y": h / 2, "fill": args.get("color", DEFAULT_FOG),
                          "opacity": opacity, "screenLock": True, "locked": False})
            ctx.insert(comp_id, "layers", sheet, [l["id"] for l in ctx.item(comp_id)["layers"]].index(id_) + 1)
