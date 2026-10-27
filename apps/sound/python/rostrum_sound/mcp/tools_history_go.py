"""`edit_history_go`: make the song stand as right after one history step again, by taking back the steps since (and
bringing back ones taken back, when the step is later than where the song stands). An undo of those steps at once; nothing is
deleted, the steps after it stay in History. Your undo is yours: an agent may only go back over its own steps.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import history_go


def register(tools: Tools):
    @tools.tool("edit_history_go", {"required": ["to"], "properties": {
        "to": {"type": "integer", "minimum": 0, "description": "The history step to stand at again (inspect_history lists them; 0 = the empty start)."},
        "item": {"type": "string", "description": "The song's item id. Optional when only one is open."}}})
    def edit_history_go(ctx, args):
        """Go back to a point in the song's history: the song as it was right after step `to`, made by taking back every step since (an undo of all of them at once: they stay in History, taken back, and going to a later step brings them back; edit_undo afterwards goes on back, it does not undo the going). Only over your own steps: if the person or another agent changed something since, it is refused and names their step (ask the person to use History, or take back only yours with edit_undo). Check what it did with inspect_note_changes."""
        doc = ctx.document(args.get("item"))
        back, forth = history_go.plan(doc, args["to"])
        others = [c for c in back + forth if c.who != ctx.who]
        if others:
            c = others[-1]
            raise RostrumError(codes.CONFLICT, "edit_history_go", f"step {args['to']}",
                               f"is behind a change by {c.who.words()} (step {c.seq}, \"{c.label}\")",
                               hint="Your undo is yours: ask the person to go back in History, or take back only your own steps with edit_undo.")
        made = history_go.go_to(doc, args["to"], ctx.who)
        if not made:
            return Reply(f"The song already stands as right after step {args['to']}.", {"seq": doc.seq})
        n = sum(len(c.undoes) + len(c.redoes) for c in made)
        return Reply(f"{made[-1].label}: {n} step{'s' * (n != 1)} taken back or brought back (change {made[-1].seq}).",
                     {"seq": made[-1].seq, "steps": [c.seq for c in made]},
                     changed={"seq": made[-1].seq, "ops": [], "group": made[-1].session})
