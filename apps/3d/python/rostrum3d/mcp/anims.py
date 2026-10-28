"""inspect_animations (anim.list): a scene item's animations as the timeline shows them (rostrum3d/anims.py, the one
source the screen's stretches read too). Facts, never changes."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from ..anims import animations
from .shot import ITEM_SHOT

tools = Tools()


@tools.tool("inspect_animations", {"required": ["owner"], "properties": {
    "item": ITEM_SHOT["item"],
    "owner": {"type": "string", "description": "The scene item's id."}}})
def inspect_animations(ctx, args):
    """An item's animations as the timeline shows them: per setting its keys and stretches (ids, start, length, ease). Ease
    with anim.ease, move keys with key.set."""
    doc = ctx.document(args.get("item"))
    anims = animations(doc.item(args["owner"]))
    words = [f'{a["label"]} {a["start"]:g}–{a["end"]:g} s (line {a["line"] + 1}, {len(a["stretches"])} stretches)' for a in anims]
    return Reply(f'{args["owner"]}: {len(anims)} animations' + (": " + "; ".join(words) if words else "") + ".",
                 {"owner": args["owner"], "animations": anims})
