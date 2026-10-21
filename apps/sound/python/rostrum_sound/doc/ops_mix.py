"""The mix: effects (on a track, a clip or the master), automation lanes, markers and the master bus."""
from __future__ import annotations

from rostrum_core import Param, codes

from . import effects as FX
from . import fields as FD
from . import ids
from . import lanes as LN
from . import values as V
from .registry import REGISTRY, set_fields, taken

INSERTS = ("track", "clip", "bus", "master")

REGISTRY.operation("master.set", "Change the master bus: level, loudness target, true peak, glue, spaces, fades.",
                   target="master", params=FD.params("master"), label="Edit master", fields=True)(set_fields)
REGISTRY.operation("effect.set", "Change an effect's settings.", target="effect", params=FD.params("effect"),
                   label="Edit effect", fields=True)(set_fields)
REGISTRY.operation("marker.set", "Rename or move a marker.", target="marker", params=FD.params("marker"),
                   label="Edit marker", fields=True)(set_fields)


@REGISTRY.operation("effect.add", "Add an effect to the end of a track's, clip's, bus' or the master's inserts.",
                    target=INSERTS, label="Add effect", params=[
                        Param.choice("effect", FX.TYPES, label="Effect type", required=True),
                        Param.text("id", label="Id", help="Optional; counted per place (pad.eq_1 …)."),
                        *FD.params("effect")[1:]])
def effect_add(ctx, targets, args):
    args = dict(args)
    for t in targets:
        id_ = args.pop("id", None) or ids.effect(t, args["effect"], taken(ctx))
        if id_ in taken(ctx):
            ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
        ctx.insert(t, "effects", {"id": id_, "type": "effect", "bypass": False, **FX.defaults(args["effect"]), **args})


def _point(p, v, where):
    if not (isinstance(v, (list, tuple)) and len(v) == 2):
        V._bad(p, v, where, "is not a point", ["[time, value]"])
    V._time(p, v[0], where)
    if isinstance(v[1], bool) or not isinstance(v[1], (int, float)):
        V._bad(p, v, where, "needs a number value")
    return list(v)


POINTS = V.listof("points", _point, {"type": "array", "minItems": 2, "maxItems": 2}, required=True,
                  help="[[time, value], …] in time order; an empty list removes the lane.")


@REGISTRY.operation("automation.set", "Replace a lane's points: anything that can change over time. On a track, "
                    "bus or the master: volume, pan, expression (dynamics 0 … 2, vibrato 0 … 1, like CC 11 / CC 1); on a "
                    "send: level (0 … 4); on an effect: any setting that takes an envelope (threshold, ratio, makeup, "
                    "mix, feedback, drive, width …), an EQ band's freq / gain / q as \"band<n>.<setting>\" (\"band1.gain\", "
                    "bands counted from 1) or a plug-in's parameter as \"param:<id>\".",
                    target=LN.TARGETS, label="Automate", params=[
                        Param.text("lane", required=True, label="Value",
                                   help="What changes: volume, pan, level, an effect setting's name, or param:<id>."),
                        POINTS])
def automation_set(ctx, targets, args):
    lane, pts = args["lane"], args["points"]
    for t in targets:
        item = ctx.item(t)
        if not LN.accepts(item, lane):
            ctx.fail(codes.BAD_ARGUMENT, f'lane "{lane}"', f"can't be automated on {t}", LN.offered(item))
        if item["type"] == "effect":
            if pts or LN.points(item, lane):
                ctx.set(t, *LN.effect_value(item, lane, pts))
            continue
        id_ = ids.lane(t, lane)
        if id_ in taken(ctx):
            if pts:
                ctx.set(id_, "points", pts)
            else:
                ctx.remove(id_)
        elif pts:
            ctx.insert(t, "automation", {"id": id_, "type": "automation", "lane": lane, "points": pts})


@REGISTRY.operation("marker.add", "Add a named time (\"drop\") that times elsewhere can name as \"#drop\".",
                    label="Add marker", params=[Param.text("id", label="Id"), *FD.params("marker", required=True)])
def marker_add(ctx, targets, args):
    id_ = args.get("id") or ids.marker(args["name"])
    if id_ in taken(ctx):
        ctx.fail(codes.BAD_ARGUMENT, f'marker "{args["name"]}"', "already exists")
    ctx.insert("root", "markers", {"id": id_, "type": "marker", "name": args["name"], "at": args["at"]})


def _remover(kind):
    def remove(ctx, targets, args):
        for t in targets:
            ctx.remove(t)
    REGISTRY.operation(f"{kind}.remove", f"Delete {kind}s.", target=kind, label=f"Delete {kind}",
                       importance="secondary")(remove)


_remover("effect")
_remover("marker")
