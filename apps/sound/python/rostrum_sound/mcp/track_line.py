"""inspect_item on a track ends with how it is played: "Feel: swing 0.55 on 8ths." (or "no swing (played straight)"),
read from the track's perform field (ears/swing.py), so an agent can read back the swing a script or track.feel set.
The values (data) hold the whole perform object as before."""
from __future__ import annotations

import dataclasses

from rostrum_core import RostrumError
from rostrum_core.conditions import holds

from ..doc.playing import PLAYED
from ..ears import swing as SW


def with_track_feel(runtime) -> None:
    old = runtime.tools.get("inspect_item")

    def wrapped(ctx, args):
        reply = old.fn(ctx, args)
        if args.get("id") in (None, "root"):
            return reply
        try:
            part = ctx.document(args.get("item")).item(args["id"])
        except RostrumError:
            return reply
        if part.get("type") == "track" and holds(PLAYED, part):
            reply.summary = f"{reply.summary} Feel: {SW.words(part)}."
            s = SW.set_on(part)
            reply.data = {**reply.data, "swing": {"swing": s[0], "swingGrid": s[1]} if s else None}
        return reply
    runtime.tools._tools["inspect_item"] = dataclasses.replace(old, fn=wrapped)
