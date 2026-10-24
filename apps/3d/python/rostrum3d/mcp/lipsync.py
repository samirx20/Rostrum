"""inspect_voice_lines: the project's voice lines as lip sync lists them (RostrumSound's own), so an agent can pick the
`line` for lipsync.make. Facts only: changes nothing."""
from __future__ import annotations

from rostrum_core.lipsync import voice
from rostrum_core.mcp import Reply, Tools

from .. import mouths
from .shot import ITEM_SHOT

tools = Tools()


@tools.tool("inspect_voice_lines", {"properties": {"item": ITEM_SHOT["item"]}})
def inspect_voice_lines(ctx, args):
    """The voice lines of the project's RostrumSound songs: id ("<song>/<line id>", what lipsync.make takes as `line`), the
    words, where the line starts in seconds, and whether its voice is made yet (a line without a voice can't be lip-synced:
    Make voice in RostrumSound). Also lists the mouths of this scene (groups whose children are named as mouth shapes) and
    the shape each child stands for."""
    doc = ctx.document(args.get("item"))
    lines = voice.lines(ctx.app.folder)
    found = [{"group": g["id"], "shapes": mouths.guess(g)} for g in _groups(doc.data) if mouths.is_mouth(g)]
    said = "; ".join(f'{ln["id"]} "{ln["text"]}" at {ln["at"]:g} s' + ("" if ln["file"] else " (no voice yet)") for ln in lines)
    return Reply(f'{len(lines)} voice lines' + (": " + said if said else " (write one in RostrumSound)") + f'. {len(found)} mouths in the scene.',
                 {"lines": lines, "mouths": found})


def _groups(node):
    for c in node.get("items", node.get("children", [])):
        yield c
        yield from _groups(c)
