"""Routing: buses, a track's sends to them, and a track's ducks (sidechain dips under other tracks).

A bus is a mixing channel several tracks feed (a "reverb" bus with a reverb insert, a "music" bus): it has its own
fader, pan, mute, inserts and automation. A track's `output` picks the bus it plays to; its sends feed more buses.
Ducks live on the ducked track; to duck a whole bus, duck each track that feeds it.
"""
from __future__ import annotations

from rostrum_core import Param, codes, did_you_mean
from rostrum_core import ids as core_ids

from .. import names
from . import fields as FD
from . import ids
from .registry import REGISTRY, set_fields, taken

REGISTRY.operation("bus.set", "Change a bus: its name, fader, pan, mute or where it plays to.", target="bus",
                   params=FD.params("bus"), label="Edit bus", fields=True)(set_fields)
REGISTRY.operation("send.set", "Change a send: which bus, how much goes to it, or whether it ignores the fader.",
                   target="send", params=FD.params("send"), label="Edit send", fields=True)(set_fields)
REGISTRY.operation("duck.set", "Change a duck: what it ducks under, how deep, how fast it dips and returns.",
                   target="duck", params=FD.params("duck"), label="Edit duck", fields=True)(set_fields)


def buses(ctx) -> list[str]:
    return [b["id"] for b in ctx.doc.get("buses", [])]


def need_bus(ctx, bus, what):
    if bus not in buses(ctx):
        ctx.fail(codes.NOT_FOUND, f'{what} bus "{bus}"', "is not a bus in this document", buses(ctx),
                 did_you_mean(bus, buses(ctx)))


@REGISTRY.operation("bus.add", "Add a bus: a channel tracks play or send into (give it effects with effect.add on "
                    "the bus; route a track to it with track.set output, or send.add).", label="Add bus", params=[
                        Param.text("id", label="Id", help="Optional; counted when left out (bus_1 …)."),
                        *FD.params("bus")])
def bus_add(ctx, targets, args):
    args = dict(args)
    id_ = args.pop("id", None) or core_ids.counted(taken(ctx), "bus")
    if id_ in taken(ctx):
        ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
    if args.get("output", names.MASTER_OUT) != names.MASTER_OUT:
        need_bus(ctx, args["output"], "output")
    ctx.insert("root", "buses", {"id": id_, "type": "bus", "name": args.pop("name", id_), **FD.DEFAULTS["bus"],
                                 **args, "effects": [], "automation": []})


@REGISTRY.operation("bus.remove", "Delete a bus and its effects; fails while a track plays to it, sends to it or "
                    "another bus feeds it (move those first).", target="bus", label="Delete bus", importance="secondary")
def bus_remove(ctx, targets, args):
    for t in targets:
        users = [f"track {x['id']}" for x in ctx.doc.get("tracks", []) if x.get("output") == t]
        users += [f"send {s['id']}" for x in ctx.doc.get("tracks", []) for s in x.get("sends", []) if s.get("bus") == t]
        users += [f"bus {b['id']}" for b in ctx.doc.get("buses", []) if b.get("output") == t]
        if users:
            ctx.fail(codes.CONFLICT, f'bus "{t}"', "is still used by " + ", ".join(users), users)
        ctx.remove(t)


@REGISTRY.operation("send.add", "Send some of a track to a bus (the way a reverb bus is fed); one send per bus.",
                    target="track", label="Add send", params=[
                        Param.text("bus", label="Bus", required=True, help="The bus id."), *FD.params("send")[1:]])
def send_add(ctx, targets, args):
    for t in targets:
        need_bus(ctx, args["bus"], "send to")
        track = ctx.item(t)
        if any(s["bus"] == args["bus"] for s in track.get("sends", [])):
            ctx.fail(codes.CONFLICT, f'track "{t}"', f'already sends to "{args["bus"]}" (change it with send.set)')
        id_ = f'{t}.send_{args["bus"]}'
        ctx.insert(t, "sends", {"id": id_, "type": "send", **FD.DEFAULTS["send"], **args, "automation": []})


@REGISTRY.operation("duck.add", "Duck a track under other tracks: it dips while they sound (music under a voice). "
                    "To duck a bus, duck each track that feeds it.", target="track", label="Add duck",
                    params=FD.params("duck", required=True))
def duck_add(ctx, targets, args):
    for t in targets:
        id_ = ids.effect(t, "duck", taken(ctx))
        ctx.insert(t, "ducks", {"id": id_, "type": "duck", **FD.DEFAULTS["duck"], **args})


def _remover(kind, summary):
    def remove(ctx, targets, args):
        for t in targets:
            ctx.remove(t)
    REGISTRY.operation(f"{kind}.remove", summary, target=kind, label=f"Delete {kind}", importance="secondary")(remove)


_remover("send", "Delete sends (the track stops feeding that bus).")
_remover("duck", "Delete ducks (the track stops dipping).")
