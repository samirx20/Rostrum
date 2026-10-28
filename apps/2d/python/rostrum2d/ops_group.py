"""Select first, then act: `group.make` wraps the selected layers in a new group, `group.release` takes a group apart,
`rig.make` wraps them in a rig. Each is one change, and every layer stays exactly where it is on screen and in time
(a group's layers sit in the group's own px, from its box's top-left corner, so moving in or out bakes the group's
place, scale, turn and opacity into each layer). What can't be done exactly is refused with the reason.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from . import boxes, fields as F
from .exprbake import source_of
from .kind import REGISTRY as R
from .names import unique_name
from .ops_items import ID, _names, new_item
from .ops_path import to_parent
from .retime import END, END_OF_COMP, FIELD

AS = {"group": "Group", "clip": "Clip", "layout": "Layout", "swap": "Swap set"}
AS_SET = {"clip": {"clip": True}, "layout": {"layout": "row", "sizeW": "fit", "sizeH": "fit"}, "swap": {"swap": True}}
HOLDERS = ("comp", "group", "rig")          # what layers can be wrapped inside (in a rig, the new group takes over their bind)
PLACE = ("x", "y", "scale", "rotation", "opacity", "anchorX", "anchorY", "scaleX", "scaleY")
PLAIN = {"blend": "normal", "matte": "", "depth": 0.0, "screenLock": False, "clip": False, "layout": "none", "swap": False,
         "start": 0.0, "end": END_OF_COMP, FIELD: "", END: "", "tiltX": 0.0, "tiltY": 0.0,
         "adjust": False, "levels": False, "curves": False, "lut": "", "ridePath": ""}   # what a group may have and still be released
PATH_LINKS = ("pathLayer", "ridePath")      # a text following / a layer riding a path layer: it must stay beside it (follow.py)
AT = Param.number("at", label="Measured at", min=0, max=36000, unit=" s", importance="deep",
                  help="The time (own seconds) the layers' box is measured at; 0 when left out")


def _value(item: dict, prop: str):
    p = F.param(item["type"], prop)
    return item.get(prop, p.default if p else None)


def _flat(deg: float) -> bool:
    """Turned by a multiple of 180 degrees: a stretch along the axes stays a stretch (no skew)."""
    return abs(math.sin(math.radians(deg))) < 1e-9


def _upright(deg: float) -> bool:
    return _flat(deg) and math.cos(math.radians(deg)) > 0


def make_group(ctx, ids: list[str], type_: str, name: str, args: dict) -> str:
    """Wrap `ids` (layers of one stack) in a new `type_` item sized to their combined box; returns its id."""
    idx = index(ctx.doc, ctx.kind.lists)
    locs = [idx[i] for i in ids]
    if len({l.parent for l in locs}) > 1:
        ctx.fail(codes.BAD_ARGUMENT, f"target {ids}", "are in different groups",
                 hint="Move them into one group or the composition first (layer.arrange).")
    parent = ctx.item(locs[0].parent)
    if parent["type"] not in HOLDERS:
        ctx.fail(codes.BAD_ARGUMENT, f'target "{ids[0]}"', f"is inside a {parent['type']}; only layers of a composition or a group can be wrapped")
    if parent.get("layout", "none") != "none":
        ctx.fail(codes.BAD_ARGUMENT, f'target "{ids[0]}"', f"is placed by {parent['id']}'s auto layout, which a new group would change",
                 hint="Turn the layout off first.")
    items = [l.item for l in locs]
    for it in items:
        if it["type"] == "camera":
            ctx.fail(codes.BAD_ARGUMENT, f'target "{it["id"]}"', "is the frame; it stays on its scene")
        if it.get("matte") and it["matte"] not in ids:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{it["id"]}"', f'is seen through the matte "{it["matte"]}", which is not selected too')
        for link in PATH_LINKS:
            if it.get(link) and it[link] not in ids:
                ctx.fail(codes.BAD_ARGUMENT, f'target "{it["id"]}"', f'follows the path layer "{it[link]}", which is not selected too')
        for p in ("x", "y"):
            if source_of(it, p):
                ctx.fail(codes.CONFLICT, f'{it["id"]}.{p}', f"is driven by an expression ({source_of(it, p)}), which would no longer fit",
                         hint="expr.clear it first.")
    for sib in parent["layers"]:
        if sib["id"] not in ids and sib.get("matte") in ids:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{sib["matte"]}"', f'is the matte of "{sib["id"]}", which is not selected too')
        for link in PATH_LINKS:
            if sib["id"] not in ids and sib.get(link) in ids:
                ctx.fail(codes.BAD_ARGUMENT, f'target "{sib[link]}"', f'is the path "{sib["id"]}" follows, which is not selected too')
    x0, y0, x1, y1 = (f(v) for f, v in zip((min, min, max, max), zip(*(boxes.box(it, args.get("at", 0.0)) for it in items))))
    w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    group = new_item(ctx, type_, {k: v for k, v in args.items() if k == "id"} | {"name": unique_name(_names(ctx), name)})
    group.update(x=x0 + w / 2, y=y0 + h / 2, w=w, h=h)
    ctx.insert(parent["id"], "layers", group, max(l.index for l in locs) + 1)
    for l in sorted(locs, key=lambda l: l.index):
        it = l.item
        for prop, off in (("x", x0), ("y", y0)):
            ctx.set(it["id"], prop, round(_value(it, prop) - off, 6))
            for k in it.get("keys", []):
                if k["prop"] == prop:
                    ctx.set(k["id"], "v", round(k["v"] - off, 6))
        ctx.move(it["id"], group["id"], "layers")
    if parent["type"] == "rig":
        _rebind(ctx, parent, ids, group["id"])
    return group["id"]


def _rebind(ctx, rig: dict, ids: list[str], group: str) -> None:
    """Layers wrapped inside a rig leave its own list, so their binds go; the new group follows the bone most of them
    followed (rigid), so the set still moves with the character."""
    gone = [b for b in rig.get("binds", []) if b["layer"] in ids]
    for b in gone:
        ctx.remove(b["id"])
    bones = [b["bone"] for b in gone]
    if bones:
        bind = new_item(ctx, "bind", {"name": f"{ctx.item(group)['name']} → bone"})
        bind.update(layer=group, bone=max(set(bones), key=bones.count))
        ctx.insert(rig["id"], "binds", bind)


@R.operation("group.make", "Select layers, then wrap them in a new group (they must be in the same group or composition). "
             "The group is sized to their combined box at `at` (its centre is the group's turning point; the screen measures at the "
             "playhead, as Figma frames and After Effects' centre-of-selection do: give the time the layers are fully in view, "
             "or animated layers may stick out) and every layer stays exactly where it is, on screen and in time; "
             "the group takes the place of the topmost one in the stack. `as`: group (plain), clip (hides what is outside "
             "its box), layout (arranges its layers in a row) or swap (shows one layer at a time).",
             target=F.PLACED, label="Group",
             params=[Param.choice("as", list(AS), label="Make", default="group",
                                  labels={"group": "Group", "clip": "Clip", "layout": "Auto layout", "swap": "Swap set"}), ID, AT])
def group_make(ctx, targets, args):
    kind = args.get("as", "group")
    gid = make_group(ctx, targets, "group", AS[kind], args)
    for field, value in AS_SET.get(kind, {}).items():
        ctx.set(gid, field, value)


@R.operation("rig.make", "Select layers (the parts of a character), then wrap them in a new rig; add its bones, IK chains and "
             "binds afterwards. The rig is sized to their combined box and every layer stays exactly where it is. One "
             "plain group (a PSD's parts) becomes the rig itself: its layers go straight into the rig, which takes its name.",
             target=F.PLACED, label="Make rig", importance="secondary", params=[ID, AT])
def rig_make(ctx, targets, args):
    name = "Rig"
    if len(targets) == 1 and ctx.item(targets[0])["type"] == "group" and not ctx.item(targets[0]).get("swap"):
        g = ctx.item(targets[0])
        if _why_not(g, ctx.item(index(ctx.doc, ctx.kind.lists)[g["id"]].parent)) is None:
            name, kids = g.get("name") or name, [k["id"] for k in g.get("layers", [])]
            group_release(ctx, [g["id"]], {})
            targets = kids
    make_group(ctx, targets, "rig", name, args)


# ---- taking a group apart -------------------------------------------------------------------------------------------
def _why_not(g: dict, parent: dict) -> str | None:
    """Why this group can't be taken apart without something jumping (None when it can)."""
    if g.get("effects") or g.get("masks"):
        return "has effects or masks, which would be lost; remove them first (effect.remove)"
    for prop, plain in PLAIN.items():
        if _value(g, prop) != plain:
            return f'has "{prop}" set ({_value(g, prop)!r}), which would be lost'
    if any(k["prop"] in PLACE for k in g.get("keys", [])) or any(source_of(g, p) for p in PLACE):
        return "is animated (keys or an expression on its place, scale, turn or opacity); its layers would jump"
    if parent["type"] not in ("comp", "group") or parent.get("layout", "none") != "none":
        return "is inside something that holds it specially (a rig or an auto layout)"
    if any(s.get("matte") == g["id"] for s in parent["layers"]):
        return "is the matte of another layer"
    return None


def _bake(ctx, g: dict, child: dict) -> None:
    """Write the group's place, scale, turn and opacity into one layer of it (its keys too)."""
    gv = F.defaults("group") | g
    sx, sy = gv["scale"] * gv["scaleX"], gv["scale"] * gv["scaleY"]
    uniform, cid, keyed = abs(sx - sy) < 1e-9, child["id"], {k["prop"] for k in child.get("keys", [])}
    if not uniform and not (_flat(gv["rotation"]) and _flat(_value(child, "rotation"))):
        ctx.fail(codes.BAD_ARGUMENT, f'target "{g["id"]}"', f'is stretched unevenly and turned, and "{cid}" is turned: it would be skewed')
    if child.get("tiltX") or child.get("tiltY") or g.get("tiltX") or g.get("tiltY"):
        ctx.fail(codes.BAD_ARGUMENT, f'target "{g["id"]}"', f'or "{cid}" is tilted (2.5D); it can\'t be baked')
    if (src := next((p for p in PLACE if source_of(child, p)), None)):
        ctx.fail(codes.CONFLICT, f"{cid}.{src}", f"is driven by an expression ({source_of(child, src)}); expr.clear it before releasing {g['id']}")
    maps = {"opacity": lambda v: v * gv["opacity"], "rotation": lambda v: v + gv["rotation"]}
    if uniform:
        maps["scale"] = lambda v: v * sx
    else:
        maps["scaleX"], maps["scaleY"] = (lambda v: v * sx), (lambda v: v * sy)
    if _upright(gv["rotation"]):
        maps["x"] = lambda v: gv["x"] + sx * (v - gv["anchorX"] * gv["w"])
        maps["y"] = lambda v: gv["y"] + sy * (v - gv["anchorY"] * gv["h"])
    elif keyed & {"x", "y"}:
        ctx.fail(codes.BAD_ARGUMENT, f'target "{g["id"]}"', f'is turned and "{cid}" has position keys, which would no longer line up')
    else:
        px, py = to_parent(gv)(_value(child, "x"), _value(child, "y"))
        maps["x"], maps["y"] = (lambda v: px), (lambda v: py)
    for prop, fn in maps.items():
        ctx.set(cid, prop, round(fn(_value(child, prop)), 6))
        for k in child.get("keys", []):
            if k["prop"] == prop:
                ctx.set(k["id"], "v", round(fn(k["v"]), 6))


@R.operation("group.release", "Take groups apart: their layers go back to where the group was in the stack and stay exactly "
             "where they are on screen (the group's place, scale, turn and opacity are baked into each layer; where layers "
             "overlap, a group of less than full opacity would have blended them differently). Refused, saying why, for a "
             "group with effects, masks, keys or an expression on its place / scale / turn / opacity, a clip, auto layout, swap "
             "set, matte, blend, colour change or timing of its own, or one stretched unevenly and turned.",
             target=("group",), label="Ungroup")
def group_release(ctx, targets, args):
    for t in targets:
        g, loc = ctx.item(t), index(ctx.doc, ctx.kind.lists)[t]
        if (why := _why_not(g, ctx.item(loc.parent))):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', why)
        kids = list(g.get("layers", []))
        for child in kids:
            _bake(ctx, g, child)
        for i, child in enumerate(kids):
            ctx.move(child["id"], loc.parent, "layers", loc.index + i)
        ctx.remove(t)
