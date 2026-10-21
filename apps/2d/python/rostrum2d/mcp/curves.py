"""inspect_curve: a number field's value curve over time, with its keys and Bézier handles (no rendering)."""
from __future__ import annotations

from rostrum_core.errors import RostrumError
from rostrum_core.mcp import Reply, Tools

from rostrum_core.keys import animated
from ..ops_keys import curve_of
from .pick import ITEM_COMP

tools = Tools()


@tools.tool("inspect_curve", {"required": ["owner", "prop"], "properties": {
    "item": ITEM_COMP["item"],
    "owner": {"type": "string", "description": "The id of the layer, effect or mask that owns the field."},
    "prop": {"type": "string", "description": "The animated number field (x, opacity, scale …)."},
    "per_stretch": {"type": "integer", "minimum": 2, "maximum": 200, "description": "Samples between two keys. Default 24."}}})
def inspect_curve(ctx, args):
    """The value curve of an animated number field: samples [[seconds, value] …] from the one evaluation, and each key
    with its ease and, where the ease is a Bézier (a named cubic or custom), its handles {x1, y1, x2, y2} for the stretch to
    the next key. Shape a stretch with the key.handles operation (its ease becomes custom); spring, bounce, hold and linear
    have no handles. A colour field has no value curve."""
    doc = ctx.document(args.get("item"))
    owner = doc.item(args["owner"])
    if args["prop"] not in animated(owner):
        raise RostrumError.not_found(ctx.tool, "animated field", args["prop"], sorted(animated(owner)), f"the animated fields of {args['owner']}")
    try:
        curve = curve_of(owner, args["prop"], args.get("per_stretch", 24))
    except ValueError as e:
        raise RostrumError.not_found(ctx.tool, "number field", args["prop"], [], str(e))
    ks = curve["keys"]
    lo, hi = min(k["v"] for k in ks), max(k["v"] for k in ks)
    words = [f'{k["t"]:g} s = {k["v"]:g} ({k["ease"]}{" " + str(list(k["handles"].values())) if k["handles"] else ""})' for k in ks]
    return Reply(f'{args["owner"]}.{args["prop"]}: {len(ks)} keys, values {lo:g} to {hi:g}: ' + "; ".join(words) + ".",
                 {"owner": args["owner"], "prop": args["prop"], "range": [lo, hi], **curve})
