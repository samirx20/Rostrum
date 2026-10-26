"""The marker document's operations, its check and its kind (see markers.py for the list of operations)."""
from __future__ import annotations

import re

from . import links
from .errors import codes
from .kind import DocKind
from .params import Param
from .registry import Registry
from .marker_times import EXT, _key


ITEM = "markers"                    # docs/markers.mkr, .rostrum/markers.history.jsonl (marker_times.py reads it)
REGISTRY = Registry()
_AT = dict(label="Time", unit="s", min=0, max=86400, step=0.01, group="Marker")
_REF = re.compile(r"^(?P<name>.+?)\s*(?P<off>[+-]\s*\d+(\.\d+)?)?$")


@REGISTRY.operation("marker.add", "Add a named marker at a time (seconds on the project timeline).", params=[
    Param.text("name", label="Name", required=True, group="Marker"),
    Param.number("at", required=True, **_AT),
    Param.text("id", label="Id", help="Optional; made from the name when left out."),
    Param.choice("owner", ["2d", "sound", "3d", "edit"], label="Made in", help="The app it belongs to (optional)."),
    Param.color("colour", label="Colour", group="Marker", importance="secondary")], label="Add marker")
def marker_add(ctx, targets, args):
    slug = re.sub(r"[^a-z0-9]+", "_", _key(args["name"])).strip("_") or "marker"
    id_ = args.get("id") or ctx.new_id(f"mk_{slug}")
    extra = {k: args[k] for k in ("owner", "colour") if args.get(k)}
    ctx.insert("root", "markers", {"id": id_, "type": "marker", "name": args["name"].strip(), "at": args["at"],
                                   **extra})


@REGISTRY.operation("marker.colour", "Change markers' colour.", target="marker", label="Marker colour",
                    importance="secondary", params=[Param.color("colour", label="Colour", required=True)])
def marker_colour(ctx, targets, args):
    for t in targets:
        ctx.set(t, "colour", args["colour"])


@REGISTRY.operation("marker.move", "Move markers to a new time.", target="marker", label="Move marker",
                    params=[Param.number("at", required=True, **_AT)])
def marker_move(ctx, targets, args):
    for t in targets:
        f = ctx.item(t).get("follows")
        if f:
            ctx.fail(codes.BAD_ARGUMENT, f'marker "{ctx.item(t)["name"]}"', f'follows "{f["part"]}" in "{f["item"]}"; '
                     "it moves with it", hint="Move that instead, or marker.unfollow first.")
        ctx.set(t, "at", args["at"])


_SET_AS = {"at": "marker.move", "name": "marker.rename", "colour": "marker.colour"}
REGISTRY.alias("marker.set", expand=lambda call: [{**call, "op": op, "args": {k: v}} for k, v in call["args"].items()
                                                  for op in [_SET_AS.get(k, "marker.move")]] or [{**call, "op": "marker.move"}],
               note='marker.set is written marker.move here (marker.rename for a name, marker.colour for a colour): '
                    'a marker moves with the one name in every app, and I ran it as that.')


@REGISTRY.operation("marker.keep", "Put following markers back on their item's time (links.refresh does this).",
                    target="marker", label="Markers follow their items", importance="deep",
                    params=[Param.number("at", required=True, **_AT)])
def marker_keep(ctx, targets, args):
    for t in targets:
        if not ctx.item(t).get("follows"):
            ctx.fail(codes.BAD_ARGUMENT, f'marker "{ctx.item(t)["name"]}"', "follows nothing", hint="Use marker.move.")
        ctx.set(t, "at", args["at"])


@REGISTRY.operation("marker.follow", "Keep a marker on another app's item: a part's start or end (a live link, "
                    "links.py). It moves whenever that part moves, even with its app closed.", target="marker",
                    label="Follow", importance="deep", params=[
                        Param.text("item", label="Item", required=True, help="The project item (\"scene1\")"),
                        Param.text("part", label="Part", required=True, help="Its part (a 2D layer id)"),
                        Param.choice("use", links.USES, label="At its", default="start")])
def marker_follow(ctx, targets, args):
    for t in targets:
        ctx.set(t, "follows", {"item": args["item"], "part": args["part"], "use": args.get("use", "start")})


@REGISTRY.operation("marker.unfollow", "Let following markers stand on their own (they stay where they are).",
                    target="marker", label="Stop following", importance="deep")
def marker_unfollow(ctx, targets, args):
    for t in targets:
        if ctx.item(t).get("follows"):
            ctx.set(t, "follows", None)


@REGISTRY.operation("marker.rename", "Rename a marker; what points at it by id keeps working.", target="marker",
                    label="Rename marker", params=[Param.text("name", label="Name", required=True, group="Marker")])
def marker_rename(ctx, targets, args):
    for t in targets:
        ctx.set(t, "name", args["name"].strip())


@REGISTRY.operation("marker.remove", "Delete markers.", target="marker", label="Delete marker",
                    importance="secondary")
def marker_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)


def _check(data) -> list[str]:
    out, seen = [], {}
    for m in data.get("markers", []):
        k = _key(m.get("name", ""))
        if not k:
            out.append(f'marker {m["id"]} has no name')
        elif k in seen:
            out.append(f'two markers are called "{m["name"]}" ({seen[k]} and {m["id"]}); names must differ')
        seen.setdefault(k, m["id"])
        f = m.get("follows")
        if f is not None and not (isinstance(f, dict) and f.get("item") and f.get("part")
                                  and f.get("use", "start") in links.USES):
            out.append(f'marker "{m.get("name")}" follows {f!r}; it needs an item, a part and start / end')
        if not isinstance(m.get("at"), (int, float)) or m["at"] < 0:
            out.append(f'marker "{m.get("name")}" has a bad time {m.get("at")!r}; it must be 0 s or later')
    return out


KIND = DocKind(ITEM, EXT, REGISTRY, lists={"doc": ["markers"]}, check=_check,
               new=lambda: {"id": "root", "type": "doc", "markers": []})
