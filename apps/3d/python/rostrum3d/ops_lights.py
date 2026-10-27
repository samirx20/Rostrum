"""Lights placed by their highlight (SPEC §7): `light.place_highlight` moves and aims a light so its highlight lands on a
spot of a surface seen from a camera (highlight.py). The screen's Alt+click and the MCP `place_highlight` tool find the
spot and its surface direction by picking; this operation only does the geometry, so a script can call it too.
A new light's starting brightness and a strip standing on end are `light.add`'s (ops_items.py, highlight.start_values).
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import compile as C, highlight as H
from .kind import REGISTRY as R

POINT = Param.list("point", "number", label="Spot", required=True, min_items=3, max_items=3, help="The spot on the surface, world metres [x, y, z]")
NORMAL = Param.list("normal", "number", label="Surface direction", required=True, min_items=3, max_items=3,
                    help="The surface's direction at the spot [x, y, z] (any length)")
EYE = Param.list("eye", "number", label="Seen from", required=True, min_items=3, max_items=3, help="Where the camera stands, world metres [x, y, z]")
DIST = Param.number("distance", label="Distance", min=0.01, max=1e4, unit="m",
                    help="How far from the spot; kept as it is when left out (a new light: 4 × the item's size)")
BRIGHT = Param.toggle("brightness", label="Starting brightness", default=False,
                    help="Also set the intensity for this distance (a light that was just added)")


@R.operation("light.place_highlight", "Move and aim a light so its highlight, seen from `eye`, lands on `point` of a "
             "surface facing `normal` (a sun: shines straight onto it). A strip stands on end.", target="light",
             label="Place highlight", params=[POINT, NORMAL, EYE, DIST, BRIGHT], min_targets=1)
def place_highlight(ctx, targets, args):
    point, normal, eye = ([float(x) for x in args[k]] for k in ("point", "normal", "eye"))
    for t in targets:
        item = ctx.item(t)
        kind = item.get("kind", "rect")
        here = [item.get(k, 0.0) for k in ("x", "y", "z")]
        dist = args.get("distance") or max(0.05, sum((a - b) ** 2 for a, b in zip(here, point)) ** 0.5)
        try:
            values = H.place(kind, eye, point, normal, dist)
        except ValueError as e:
            ctx.fail(codes.BAD_ARGUMENT, f'light "{t}"', str(e))
        if args.get("brightness"):                      # a light just added: a panel sized for here, then its brightness
            values.update(H.fit_panel(kind, item, values, dist))
            values["intensity"] = H.start_intensity(kind, {**item, **values}, dist)
        parent = _parent(ctx.doc, t)
        if parent:
            values = H.to_parent(C.world_at_start(ctx.doc, parent), values)
        for k, v in values.items():
            ctx.set(t, k, round(v, 6) if isinstance(v, float) else v)
    return ctx.item(targets[0])


def _parent(doc: dict, id_: str) -> str:
    """The id of the group holding `id_`, "" at the top level."""
    stack = [(i, "") for i in doc.get("items", [])]
    while stack:
        item, parent = stack.pop()
        if item["id"] == id_:
            return parent
        stack += [(c, item["id"]) for c in item.get("children", [])]
    return ""
