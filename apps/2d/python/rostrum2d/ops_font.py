"""font.replace: one font for another across the document, as ONE change (one undo step): every text, and every text style,
that uses the old family. What the Problems list's "Use another font" does for a Missing font (diagnose_engine.py), and
what an agent calls for the same. The new font is checked as a font set by hand is (fontlist.setting_refusal)."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import fields as F, fontlist
from .kind import REGISTRY as R


def users(ctx, family: str) -> list[dict]:
    """The texts and text styles whose font is `family` (the field's default when they name none)."""
    default = F.defaults("text")["font"]
    return [loc.item for loc in ctx.idx.values()
            if loc.item.get("type") in ("text", "textstyle") and loc.item.get("font", default) == family]


@R.operation("font.replace", "Use another font for every text (and text style) that uses one font, in one change: a project "
             "that names a font this computer lacks (a Missing font problem) is fixed with one call. inspect_fonts lists the "
             "fonts there are.", label="Use another font",
             params=[Param.text("from", label="Font to replace", required=True),
                     Param.text("to", label="New font", required=True, help="A font the app or this computer has (inspect_fonts)")])
def font_replace(ctx, targets, args):
    found = users(ctx, args["from"])
    if not found:
        ctx.fail(codes.BAD_ARGUMENT, f'from="{args["from"]}"', "is not the font of any text in this document")
    for item in found:
        if why := fontlist.setting_refusal(item["id"], args["to"], item.get("italic", False)):
            ctx.fail(codes.BAD_ARGUMENT, f'to="{args["to"]}"', why)
    for item in found:
        ctx.set(item["id"], "font", args["to"])
