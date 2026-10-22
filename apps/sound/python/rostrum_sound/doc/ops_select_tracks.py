"""`bus.from_tracks`: select tracks, group them. One step makes the bus and points those tracks at it, so no
empty bus is ever left to fill afterwards (a summing group: the tracks' sum goes through the bus's own fader,
inserts and automation). The new bus's id is `select_time.inserted(change)[0]`.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core import ids as core_ids

from .. import names
from . import fields as FD
from .registry import REGISTRY, taken

NAME = Param.text("name", label="Name", help='What the group is called. Left out = made from the tracks ("Drums + '
                  'Bass").')


@REGISTRY.operation("bus.from_tracks", "Group the selected tracks: a new bus they all play to, made and routed in "
                    "one step. Give it effects or a fader afterwards (bus.set, effect.add).", target="track",
                    params=[NAME], label="Group tracks")
def from_tracks(ctx, targets, args):
    tracks = [ctx.item(t) for t in targets]
    names_ = [t.get("name") or t["id"] for t in tracks]
    name = args.get("name") or (" + ".join(names_) if len(names_) <= 3 else f"{names_[0]} + {len(names_) - 1} more")
    before = {t.get("output", names.MASTER_OUT) for t in tracks}
    id_ = core_ids.counted(taken(ctx), "bus")
    ctx.insert("root", "buses", {"id": id_, "type": "bus", "name": name, **FD.DEFAULTS["bus"],
                                 "output": before.pop() if len(before) == 1 else names.MASTER_OUT,
                                 "effects": [], "automation": []})
    for t in targets:
        ctx.set(t, "output", id_)
