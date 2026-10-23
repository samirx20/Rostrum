"""Operations on materials and shots. A material is one physically based surface (ENGINE_CONTRACT.md § 2
› Materials): glass, metal or paint are only values (guides/materials.md). A shot is a camera, a frame size
and a stretch of time.
"""
from __future__ import annotations

from rostrum_core import Param
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


@R.operation("shot.remove", "Delete shots (the items stay).", target="shot", label="Delete", importance="secondary")
def shot_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)
