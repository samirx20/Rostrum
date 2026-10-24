"""inspect_fonts: every font family a text can name (rostrum2d/fontlist.py, the engine's one list)."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

tools = Tools()


@tools.tool("inspect_fonts", {"properties": {"search": {
    "type": "string", "description": "Only families whose name holds this (any case), e.g. \"serif\" or \"Arial\". Default: all."}}})
def inspect_fonts(ctx, args):
    """Every font family a text's `font` may name: the fonts shipped with Rostrum2D first (source "shipped": the same on
    every computer), then the fonts installed on this computer (source "installed": another computer may not have
    them). Each with its real weights (`weights`; a variable family takes any weight in `range`), whether it has an
    italic (set the text's `italic`), and its files. A font that isn't listed is refused when set, never drawn in
    another font; a project using one that this computer lacks shows a Missing font problem, draws that text as a dashed red box naming the font, and won't export until `font.replace {from, to}` has set another font on every text that used it (one undo step)."""
    from ..fontlist import families
    want = str(args.get("search", "")).strip().lower()
    found = [f for f in families() if want in f["family"].lower()]
    shipped = [f["family"] for f in found if f["source"] == "shipped"]
    words = (f"{len(found)} famil{'y' if len(found) == 1 else 'ies'}" + (f' matching "{want}"' if want else "")
             + (f"; shipped: {', '.join(shipped)}" if shipped else "")
             + f"; installed: {sum(f['source'] == 'installed' for f in found)}")
    return Reply(words, {"families": found})
