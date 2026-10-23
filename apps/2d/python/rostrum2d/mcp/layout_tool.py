"""inspect_layout: where auto layouts put their layers at a time (no rendering), from the one solver (layout.py)."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from ..exprbake import items_of
from ..layout import has_layout, solve
from .pick import ITEM_COMP, TIME, doc_and_comp, time_of

tools = Tools()


@tools.tool("inspect_layout", {"properties": {**ITEM_COMP, **TIME, "group": {
    "type": "string", "description": "Only this laid-out group. Default: every group with an auto layout."}}})
def inspect_layout(ctx, args):
    """The auto layouts of a composition at a time: for each laid-out group its settings and each layer it places, in order,
    with x, y (the anchor, in the group's px from its top-left) and, where the layout sizes it, w and h: the values the render
    uses. Set them with group.set (layout, gap, hug …) and a layer's layoutGrow / layoutApart; a laid-out layer's x and y
    belong to the layout (set it apart to place it by hand). A group's background hugs its layers when the layout hugs."""
    doc, comp = doc_and_comp(ctx, args)
    t, _ = time_of(ctx, comp, args)
    groups = [g for g in items_of(comp).values() if has_layout(g)]
    if "group" in args:
        groups = [g for g in groups if g["id"] == args["group"]]
        if not groups:
            raise RostrumError(codes.NOT_FOUND, ctx.tool, f'group "{args["group"]}"', "has no auto layout in this composition",
                               hint="Turn one on with group.set layout=row (or column, grid).")
    placed = solve(comp, t)
    keys = ("layout", "gap", "padding", "justify", "align", "wrap", "columns", "rowGap", "hugWidth", "hugHeight", "hugPin", "background")
    rows = [{"group": g["id"], "settings": {k: g.get(k) for k in keys if k in g},
             **({"size": placed[g["id"]]} if g["id"] in placed else {}),
             "layers": [{"id": c["id"], **placed[c["id"]]} for c in g.get("layers", []) if c["id"] in placed]}
            for g in groups]
    words = "; ".join(f'{r["group"]} ({r["settings"].get("layout")}): ' + ", ".join(
        f'{c["id"]} at {c["x"]:g},{c["y"]:g}' + (f' {c["w"]:g}x{c["h"]:g}' if "w" in c else "") for c in r["layers"])
        for r in rows) or "no group has an auto layout"
    return Reply(f"At {t:g} s: {words}.", {"time": t, "groups": rows})
