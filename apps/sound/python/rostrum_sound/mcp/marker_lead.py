"""edit_markers in Sound: moving a project marker also looks after the song's lead-in (doc/ops_carry.py has the rule).

    {"op": "marker.move", "target": ["reveal"], "args": {"at": 24, "lead_in": 4}}

`lead_in` (seconds, or {"beats": n}) is Sound's own extra argument: before the marker moves, every open song's
`marker.carry` re-times what starts within that window before the marker onto it (a step in that song's own history,
so the song stays the one place a change is recorded), then the shared marker moves, and the lead-in goes with it.
Without `lead_in` nothing else moves, but the reply names what ends within a beat before the marker's old place and
stays behind ("3 notes on strings end just before #reveal and stay when it moves"). Never a silent change of what plays.
"""
from __future__ import annotations

import copy
import dataclasses

from rostrum_core import markers as M

from ..doc import markers as MK
from ..doc import ops_carry

MOVES = ("marker.move", "marker.set")
ARG_HELP = (' Sound adds `lead_in` to marker.move: seconds (4) or {"beats": 8}; what starts that far before the marker is '
            "tied to it first, so the build-up moves with it (each open song records it as marker.carry). Without it the reply "
            "names what ends just before the marker and would stay behind.")


def _moves(folder, ops: list) -> list[tuple[str, object]]:
    """[(marker name, lead_in or None)] for each marker.move call (a target is an id or a name)."""
    every = M.listing(folder)
    names = {m["id"]: m["name"] for m in every} | {M._key(m["name"]): m["name"] for m in every}
    out = []
    for call in ops:
        if call.get("op") in MOVES and "at" in (call.get("args") or {}):
            out += [(names.get(t) or names.get(M._key(t)) or t, call["args"].get("lead_in")) for t in call.get("target") or []]
    return out


def with_marker_lead(runtime) -> None:
    old = runtime.tools.get("edit_markers")

    def edit_markers(ctx, args):
        moves = _moves(ctx.app.folder, args.get("ops", []))
        ops = [{**c, "args": {k: v for k, v in c["args"].items() if k != "lead_in"}} if (c.get("args") or {}).get("lead_in") is not None else c
               for c in args.get("ops", [])]
        said = []
        for item, doc in ctx.app.documents.items():
            for name, lead in moves:
                if not MK.has(doc.data, name):
                    continue                                       # the marker doesn't exist: the shared op fails, naming them
                if lead is None:
                    if words := ops_carry.staying_words(doc.data, name):
                        said.append(f"{item}: {words}")
                elif ops_carry.window(doc.data, name, lead):
                    ctx.apply(doc, [{"op": "marker.carry", "args": {"marker": name, "lead_in": lead}}], label=f'Carry the lead-in of "{name}"')
                else:
                    said.append(f'{item}: nothing starts within {lead} before "{name}"; only the marker moves.')
        reply = old.fn(ctx, {**args, "ops": ops})
        for line in said:
            ctx.note(line)
        return reply
    schema = copy.deepcopy(old.schema)
    args_schema = schema["properties"]["ops"]["items"]["properties"]["args"]
    args_schema["description"] += ARG_HELP
    runtime.tools._tools["edit_markers"] = dataclasses.replace(old, fn=edit_markers, schema=schema)
