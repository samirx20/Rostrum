"""Shared tools for working beside a person: inspect_screen (what they see) and edit_undo (take back your own work).

Your undo is yours (INTERACTION.md 1.9): edit_undo takes back only the calling agent's own steps, never the person's.
"""
from __future__ import annotations

from .. import screen_state
from ..errors import RostrumError, codes
from .reply import Reply
from .tools import Tools

_ITEM = {"item": {"type": "string", "description": "The document's project item id. Optional when only one document is open."}}


def _said(s: dict) -> str:
    sel = s.get("selection") or []
    names = ", ".join(f'{x.get("name") or x["id"]} ({x.get("kind", "?")}, id {x["id"]})' for x in sel[:6])
    picked = f"{len(sel)} selected: {names}{' …' if len(sel) > 6 else ''}" if sel else "nothing selected"
    ph = s.get("playhead")
    rng = s.get("range")
    return (f'{s["app"]} window on "{s.get("scene") or s.get("item")}": {picked}; playhead '
            f'{f"{ph:.2f} s" if isinstance(ph, (int, float)) else "—"}'
            f'{f"; time range {rng[0]:.2f}–{rng[1]:.2f} s" if rng else ""}; focus: {s.get("focus") or "—"}'
            f'{"; the person is dragging " + ", ".join(s["dragging"]) + " right now" if s.get("dragging") else ""}.')


def register(tools: Tools):
    @tools.tool("inspect_screen", {"properties": {}})
    def inspect_screen(ctx, args):
        """What the person sees in the app's window right now: the selection (ids, kind, name, time), the playhead, the
        time range, the open scene or song, the focused area and the view. Use it for "this", "here", "the selected one"."""
        if not ctx.app.folder:
            raise RostrumError(codes.NOT_FOUND, "", "no project", "is open in this server, so there is no window to look at",
                               hint="Open the project first (inspect_project).")
        shown = screen_state.read(ctx.app.folder)
        if not shown:
            return Reply("No Rostrum window is open on this project right now, so nothing is selected.", {"windows": []})
        return Reply(" ".join(_said(s) for s in shown), {"windows": shown})

    @tools.tool("edit_undo", {"properties": {**_ITEM, "group": {"type": "string", "description":
                "Take back this whole group of your own changes in one step. Without it: your own last change."}}})
    def edit_undo(ctx, args):
        """Take back your own last change, or one whole group of yours. Never the person's or another agent's."""
        doc = ctx.document(args.get("item"))
        group = args.get("group")
        if group:
            run = [c for c in doc.history.changes if c.original and c.session == group]
            if not run:
                raise RostrumError.not_found("", "group", group, {c.session for c in doc.history.changes if c.session})
            others = {str(c.who) for c in run if c.who != ctx.who}
            if others:
                raise RostrumError(codes.CONFLICT, "", f'group "{group}"', f"holds changes by {', '.join(sorted(others))}",
                                   hint="Your undo takes back only your own changes; ask the person to use History.")
            change = doc.undo_session(group, ctx.who)
        else:
            change = doc.undo(ctx.who)
        if change is None:
            return Reply("Nothing of yours to take back.", {"seq": doc.seq})
        return Reply(f"{change.label} (change {change.seq}).", {"seq": change.seq},
                     changed={"seq": change.seq, "ops": [], "group": change.session})
