"""Operations on materials and shots. A material is one physically based surface (ENGINE_CONTRACT.md § 2
› Materials): glass, metal or paint are only values (guides/materials.md). A shot is a camera, a frame size
and a stretch of time.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.conditions import holds
from rostrum_core.errors import codes
from rostrum_core.tree import walk

from . import fields as F
from .kind import REGISTRY as R
from .ops_items import ID, NAME, new_item

USERS = ("mesh", "combine", "import", "part")      # items that name a material


@R.operation("material.add", "Add a material (one physically based surface: base colour, metallic, roughness, "
             "transmission, coat …).", label="Add material", params=[ID, NAME, *F.unconditional("material")])
def material_add(ctx, targets, args):
    fields = [p.name for p in F.FIELDS["material"]]
    ctx.insert("root", "materials", new_item(ctx, "material", args, {k: v for k, v in args.items() if k in fields}))


@R.operation("material.assign", "Give meshes, combines, imports or import parts a material (\"\" = none, or the file's own).",
             target=USERS, label="Assign material",
             params=[Param.text("material", label="Material", required=True, help='A material id, or ""')])
def material_assign(ctx, targets, args):
    if args["material"]:
        mat = ctx.item(args["material"])
        if mat["type"] != "material":
            ctx.fail(codes.BAD_ARGUMENT, f'material "{args["material"]}"', f"is a {mat['type']}, not a material")
    for t in targets:
        ctx.set(t, "material", args["material"])


@R.operation("material.remove", "Delete materials. Items that used one are left with none (in the same step, so "
             "one undo brings both back).", target="material", label="Delete", importance="secondary")
def material_remove(ctx, targets, args):
    for item in list(walk(ctx.doc, ctx.kind.lists)):
        if item.get("type") in USERS:
            for field in ("material", "frontMaterial", "bevelMaterial", "sideMaterial", "backMaterial"):
                if item.get(field) and item[field] in targets:
                    ctx.set(item["id"], field, "")
    for t in targets:
        ctx.remove(t)


@R.operation("shot.add", "Add a shot: the camera it looks through, its frame rate, start and end (seconds) and "
             "frame size.", label="Add shot", params=[ID, NAME, *F.unconditional("shot")])
def shot_add(ctx, targets, args):
    fields = [p.name for p in F.FIELDS["shot"]]
    ctx.insert("root", "shots", new_item(ctx, "shot", args, {k: v for k, v in args.items() if k in fields}))


VIEW = [Param.list("position", "number", label="Position", min_items=3, max_items=3, unit="m", required=True,
                   help="Where the camera stands (x y z)"),
        Param.list("turn", "number", label="Turn", min_items=3, max_items=3, unit="°", required=True,
                   help="Its turn rx ry rz in degrees (it looks along its −Z)"),
        Param.number("focalLength", label="Focal length", min=1, max=2000, unit="mm", default=50.0),
        Param.text("cameraId", label="Camera id", help="Optional id for the new camera; counted when left out")]


@R.operation("shot.from_view", "New shot from a view: a camera standing at `position`, turned `turn`, with "
             "`focalLength`, and a shot looking through it (named \"Shot N\"; its size, frame rate, time and render "
             "settings copied from the first shot). One step: one undo takes both back.",
             label="New shot from this view", params=[ID, NAME, *VIEW])
def shot_from_view(ctx, targets, args):
    shots = ctx.doc.get("shots", [])
    if not shots:
        ctx.fail(codes.BAD_ARGUMENT, "shots", "there is no first shot to copy the size and time from",
                 hint="Add one with shot.add first.")
    first = shots[0]
    name = args.get("name") or f"Shot {len(shots) + 1}"
    rx, ry, rz = args["turn"]
    x, y, z = args["position"]
    cam_args = {"id": args.get("cameraId"), "name": f"{name} camera"}
    camera = new_item(ctx, "camera", cam_args, {"x": x, "y": y, "z": z, "rx": rx, "ry": ry, "rz": rz,
                                                "focalLength": args.get("focalLength", 50.0)})
    ctx.insert("root", "items", camera)
    copied = {p.name: first[p.name] for p in F.FIELDS["shot"]
              if p.name in first and p.name != "camera" and holds(p.valid_when, first)}
    ctx.insert("root", "shots", new_item(ctx, "shot", {"id": args.get("id"), "name": name},
                                         {**copied, "camera": camera["id"]}))


@R.operation("shot.remove", "Delete shots (the items stay).", target="shot", label="Delete", importance="secondary")
def shot_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)
