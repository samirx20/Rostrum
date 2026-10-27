"""The material picker's operations (SPEC §6.1–6.2): a new material from a starting point (material_starts.py),
and splitting a shared material so one item can change alone. Adding, assigning and deleting are ops_scene.py.
"""
from __future__ import annotations

import copy as _copy

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import walk

from . import fields as F
from .graph import FIELD as GRAPH
from .kind import KIND, REGISTRY as R
from .material_starts import STARTS, start_values
from .ops_items import ID, NAME, new_item
from .ops_scene import USERS

FACES = ("material", "frontMaterial", "bevelMaterial", "sideMaterial", "backMaterial")   # fields that name a material
START = Param.choice("start", list(STARTS), label="Start from", required=True,
                     labels={k: s["label"] for k, s in STARTS.items()},
                     help="The substance's physical settings to begin with; change any field afterwards")
TO = Param.list("to", "id", label="Give it to", help="Meshes, combines, imports or parts that get the new material")


def users_of(doc_data: dict, material_id: str) -> list[str]:
    """The ids of the items that use a material: as their material or as a text / logo face's material."""
    return [it["id"] for it in walk(doc_data, KIND.lists)
            if it.get("type") in USERS and any(it.get(f) == material_id for f in FACES)]


def _fields(values: dict) -> dict:
    names = {p.name for p in F.FIELDS["material"]}
    return {k: v for k, v in values.items() if k in names}


@R.operation("material.from", "Make a new material from a starting point (a substance's physical settings: clay, skin, wax / soap, "
             "stone, matte or glossy plastic, rubber, polished or brushed metal, glass, frosted glass, ceramic, fabric, wood, car paint, "
             "screen); any material field given here wins over the start's value. `to`: items that get it, in the "
             "same step (one undo takes both back). Its name is \"<item> material\" for one item, else the start's "
             "name. The result is an ordinary material: change its fields with material.set.",
             label="New material from", params=[START, ID, NAME, TO, *F.unconditional("material")])
def material_from(ctx, targets, args):
    to = list(args.get("to") or [])
    for t in to:
        if ctx.item(t)["type"] not in USERS:
            ctx.fail(codes.BAD_ARGUMENT, f'to "{t}"', f"is a {ctx.item(t)['type']}, which has no material",
                     hint="Give it to meshes, combines, imports or import parts.")
    name = args.get("name") or (f'{ctx.item(to[0]).get("name") or to[0]} material' if len(to) == 1
                                else STARTS[args["start"]]["label"])
    item = new_item(ctx, "material", {"id": args.get("id"), "name": name},
                    start_values(args["start"], _fields(args)))
    ctx.insert("root", "materials", item)
    for t in to:
        ctx.set(t, "material", item["id"])
    return item


@R.operation("material.split", "Give each target its own copy of the material it shares with other items, so it can "
             "change alone: a new material with the same fields, named \"<item> material\". The other items keep the "
             "original. Refused when a target has no material or is its material's only user.",
             target=USERS, label="Make its own material", importance="secondary")
def material_split(ctx, targets, args):
    made = []
    for t in targets:
        item = ctx.item(t)
        mat_id = item.get("material")
        if not mat_id:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', "has no material to split",
                     hint="Give it one with material.assign or material.from.")
        users = users_of(ctx.doc, mat_id)
        if users == [t]:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f'is the only item using "{mat_id}"; nothing to split',
                     hint="Change the material itself with material.set.")
        mat = ctx.item(mat_id)
        copy = new_item(ctx, "material", {"name": f'{item.get("name") or t} material'}, {})
        copy.update(_copy.deepcopy(_fields(mat)))           # already checked values, copied as they are
        if mat.get(GRAPH):
            copy[GRAPH] = _copy.deepcopy(mat[GRAPH])        # its blocks graph too (graph.py)
        ctx.insert("root", "materials", copy)
        ctx.set(t, "material", copy["id"])
        made.append(copy)
    return made[0] if len(made) == 1 else made
