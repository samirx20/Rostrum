"""inspect_layout (what: swaps): which child each swap set shows at a time (no rendering), from the one rule (swap.py)."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from ..exprbake import items_of
from ..swap import index_at
from .pick import ITEM_COMP, TIME, doc_and_comp, time_of

tools = Tools()


@tools.tool("inspect_swaps", {"properties": {**ITEM_COMP, **TIME}})
def inspect_swaps(ctx, args):
    """The swap sets of a composition at a time: for each its children in order (place from 0, id, name) and the one
    showing now. The same choice the render makes (the set's `show` keys, held). Change it with swap.show, blink.add or
    lipsync.apply; a set with no children shows nothing."""
    _, comp = doc_and_comp(ctx, args)
    t, _ = time_of(ctx, comp, args)
    rows = []
    for g in items_of(comp).values():
        if g.get("type") == "group" and g.get("swap"):
            kids = g.get("layers", [])
            rows.append({"group": g["id"], "children": [{"index": i, "id": c["id"], "name": c.get("name", c["id"])}
                                                        for i, c in enumerate(kids)],
                         "shows": kids[index_at(g, t, len(kids))]["id"] if kids else None})
    words = "; ".join(f'{r["group"]} shows {r["shows"] or "nothing"} of {", ".join(c["id"] for c in r["children"])}'
                      for r in rows) or "no group is a swap set"
    return Reply(f"At {t:g} s: {words}.", {"time": t, "swaps": rows})
