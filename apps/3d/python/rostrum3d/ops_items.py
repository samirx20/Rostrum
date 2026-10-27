"""Operations that add, remove, rename, aim and arrange scene items (groups, meshes, imports, lights, cameras)
and an import's parts. Field changes are the generated `<type>.set` operations (kind.py); keys are ops_keys.py;
materials and shots are ops_scene.py.
"""
from __future__ import annotations

import copy

from rostrum_core import Param, ids
from rostrum_core.errors import codes
from rostrum_core.tree import child_keys, index, subtree_ids

from . import build, fields as F, highlight, mirror
from .kind import REGISTRY as R

ID = Param.text("id", label="Id", help="Optional; counted per type when left out (mesh_1, mesh_2 …). Letters, digits, _")
NAME = Param.text("name", label="Name")
INTO = Param.id("into", label="Into", help="A group or import to put it in; the scene's top level when left out")
INDEX = Param.number("index", label="Position", min=0, max=100000, integer=True, importance="deep",
                     help="Place in the list; the end when left out")
PLACE = [ID, NAME, INTO, INDEX]


def refuse_used_id(ctx, id_: str) -> None:
    """The one place ids are checked across the document (items, materials, shots, parts, keys): a taken id is
    refused naming what holds it ('id "top" is already used by a mesh')."""
    held = index(ctx.doc, ctx.kind.lists).get(id_)
    if held:
        what = F.LABELS.get(held.item.get("type"), "item").lower()
        ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', f"is already used by {'an' if what[0] in 'aeiou' else 'a'} {what}",
                 hint="Pick another id, or leave id out to have one counted.")


def new_item(ctx, type_: str, args: dict, field_args: dict) -> dict:
    id_ = args.get("id") or ctx.new_id(type_)
    refuse_used_id(ctx, id_)
    return build.make(type_, id_, {"name": args.get("name") or F.LABELS[type_], **field_args}, ctx.where)


def _holder(ctx, into):
    if not into:
        return "root", "items"
    holder = ctx.item(into)
    if holder["type"] not in F.HOLDERS:
        ctx.fail(codes.BAD_ARGUMENT, f'into "{into}"', f"is a {holder['type']}, not a group or import")
    return into, "children"


def _adder(type_: str, summary: str, extra=(), fill=None):
    fields = [p.name for p in F.FIELDS[type_]]

    def add(ctx, targets, args):
        given = {k: v for k, v in args.items() if k in fields}
        item = new_item(ctx, type_, args, fill(given) if fill else given)
        parent, key = _holder(ctx, args.get("into"))
        ctx.insert(parent, key, item, args.get("index"))
        return item
    return R.operation(f"{type_}.add", summary, label=f"Add {F.LABELS[type_].lower()}",
                       params=[*PLACE, *extra, *F.unconditional(type_)])(add)


_adder("group", "Add a group: items inside it move, turn and scale with it.")
_adder("mesh", "Add a mesh: a box, sphere, cylinder, cone, capsule, plane, disc or torus, or an extruded word (text), SVG drawing (svg) "
       "or 2D path layer (path2d: doc2d + layer); centred on its origin (sizes in metres, depth = extrusion).")
_adder("light", "Add a light: rect or disk panel (shines along its −Z), strip, sphere bulb, spot, distant sun or dome sky. "
       "Without an intensity it starts at a sensible brightness for its distance to what it aims at (else the "
       "scene's middle); a strip stands on end.", fill=lambda given: highlight.start_values(F.FIELDS["light"], given))
_adder("camera", "Add a camera (looks along its −Z, Y up). A shot names the camera it looks through.")
_adder("rig", "Add a camera rig (orbit / crane / dolly) at a base point; put the shot camera inside it "
       "(into=<rig id>) and key the rig's angle, lift, swing or travel. Handheld adds a gentle seeded drift.")


@R.operation("part.add", "Add a part override to an import: a prim inside its file that gets its own material or "
             "is hidden.", target="import", label="Add part",
             params=[Param.text("path", label="Path", required=True), *F.unconditional("part")[1:]])
def part_add(ctx, targets, args):
    for t in targets:
        id_ = build.part_id(t, args["path"])
        if id_ in index(ctx.doc, ctx.kind.lists):
            ctx.fail(codes.BAD_ARGUMENT, f'path "{args["path"]}"', f"already has a part on {t} ({id_})")
        ctx.insert(t, "parts", build.make("part", id_, {"name": args["path"], **args}, ctx.where))


@R.operation("item.remove", "Delete items (with everything inside them, their keys and parts, and the mirrored "
             "copies of a deleted mesh or across a deleted clay).",
             target=(*F.ITEMS, "effector", "part"), label="Delete", importance="secondary")
def item_remove(ctx, targets, args):
    gone = set()
    for t in targets:
        if t in index(ctx.doc, ctx.kind.lists):     # already gone with a removed parent: fine
            gone |= set(subtree_ids(ctx.item(t), ctx.kind.lists))
            ctx.remove(t)
    left = index(ctx.doc, ctx.kind.lists).values()
    for c in mirror.copies_of((loc.item for loc in left), gone):
        ctx.remove(c)                               # a copy goes with its original or its clay (mirror.py)
    for loc in left:                                # a part placed on a removed clay stays, standing where it was put
        if loc.item.get("followPose") and loc.item.get("follow") in gone and loc.item["id"] not in gone:
            ctx.set(loc.item["id"], "follow", "")
            ctx.set(loc.item["id"], "followPose", False)


def _reid(item: dict, new_id: str, taken: set, lists: dict):
    """Give a copy of `item` (and everything inside it) new ids: counted per type, a key's and a part's id from its
    new owner (the same rule as their own adders), so a copy never shares an id with the original."""
    old, item["id"] = item["id"], new_id
    taken.add(new_id)
    for key in child_keys(item, lists):
        for child in item[key]:
            if key == "keys":
                child["id"] = new_id + child["id"][len(old):] if child["id"].startswith(old) else ids.from_content(new_id, "k", child["t"] * 1000)
                taken.add(child["id"])
            elif key == "parts":
                child["id"] = build.part_id(new_id, child["path"])
                taken.add(child["id"])
            else:
                _reid(child, ids.counted(taken, child["type"]), taken, lists)


@R.operation("item.duplicate", "Copy an item, material or shot with its keys, children and parts, under new ids, right "
             "after the original (same list, same parent). Its transform and references stay as written.",
             target=(*F.ITEMS, "material", "shot"), label="Duplicate", importance="secondary",
             params=[ID, Param.toggle("rename", label="Name it “… copy”", default=True, importance="deep")])
def item_duplicate(ctx, targets, args):
    if args.get("id") and len(targets) != 1:
        ctx.fail(codes.BAD_ARGUMENT, '"id"', "can only be given when one item is copied")
    taken = set(index(ctx.doc, ctx.kind.lists))
    for t in targets:
        loc = index(ctx.doc, ctx.kind.lists)[t]
        if args.get("id"):
            refuse_used_id(ctx, args["id"])
        new = copy.deepcopy(loc.item)
        _reid(new, args.get("id") or ids.counted(taken, new["type"]), taken, ctx.kind.lists)
        if args.get("rename", True):
            new["name"] = f'{new.get("name") or t} copy'
        ctx.insert(loc.parent, loc.key, new, loc.index + 1)


@R.operation("item.rename", "Rename an item, material or shot (the id stays).",
             target=(*F.ITEMS, "effector", "part", "material", "shot"), label="Rename", importance="secondary",
             params=[Param.text("name", label="Name", required=True)])
def item_rename(ctx, targets, args):
    for t in targets:
        ctx.set(t, "name", args["name"])


@R.operation("item.arrange", "Move an item into another group or import, or to another place in its list. Its "
             "transform stays as written, so it is now relative to the new parent.", target=F.ITEMS,
             label="Arrange", importance="secondary",
             params=[INTO, Param.number("index", label="Position", min=0, max=100000, integer=True,
                                        help="The end when left out")])
def item_arrange(ctx, targets, args):
    for t in targets:
        loc = index(ctx.doc, ctx.kind.lists)[t]
        parent, key = _holder(ctx, args.get("into")) if "into" in args else (loc.parent, loc.key)
        if parent in subtree_ids(ctx.item(t), ctx.kind.lists):
            ctx.fail(codes.BAD_ARGUMENT, f'into "{parent}"', "is the item itself or inside it")
        ctx.move(t, parent, key, args.get("index"))


@R.operation("item.aim", "Point items' −Z (cameras, rect and disk lights face that way) at a point or at another "
             "item, every frame; or stop aiming (the written turn rx ry rz applies again).",
             target=F.ITEMS, label="Aim",
             params=[Param.list("point", "number", label="Point", min_items=3, max_items=3, unit="m"),
                     Param.id("at", label="At item"), Param.toggle("off", label="Stop aiming", importance="secondary")])
def item_aim(ctx, targets, args):
    given = [k for k in ("point", "at", "off") if args.get(k) not in (None, False)]
    if len(given) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "arguments", f"need exactly one of point, at, off (got {given or 'none'})")
    for t in targets:
        if "point" in args:
            ctx.set(t, "aim", "point")
            for axis, v in zip("XYZ", args["point"]):
                ctx.set(t, f"aim{axis}", v)
        elif "at" in args:
            ctx.item(args["at"])
            ctx.set(t, "aim", "item")
            ctx.set(t, "aimItem", args["at"])
        else:
            ctx.set(t, "aim", "none")
