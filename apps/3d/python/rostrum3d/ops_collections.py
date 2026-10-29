"""Collections (PR1, collection_kit.py): `collection.add`, `collection.set`, `collection.remove` make and change a named
set of items (a list, and / or "every item with material X"); `collection.material` gives every member a material and
`collection.show` shows or hides every member (in all shots, or in one `shot` only). A light's Lights only may name a
collection. Each is one step (one undo).
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import collection_kit as K, fields as F, shot_layer as L
from .kind import REGISTRY as R
from .ops_items import refuse_used_id

NAME = Param.text("name", label="Name")
ITEMS = Param.list("items", "text", label="Items", help="Item ids: the collection is exactly these (and its material rule)")
INCLUDE = Param.list("include", "text", label="Add items", help="Item ids added to its list")
EXCLUDE = Param.list("exclude", "text", label="Take out", help="Item ids taken off its list")
MATERIAL = Param.text("material", label="Every item with material",
                      help='A material id: every item using it is in the collection, now and later; "" = no rule')


def _real(ctx, ids_):
    for i in ids_:
        it = ctx.item(i)
        if it.get("type") not in F.ITEMS:
            ctx.fail(codes.BAD_ARGUMENT, f'"{i}"', f"is a {it.get('type')}; a collection holds scene items")
    return list(dict.fromkeys(ids_))


@R.operation("collection.add", "Make a collection: a named set of items (a list, and / or every item with a material) "
             "that a light's Lights only, collection.material and collection.show can target.",
             label="New collection", params=[Param.text("id", label="Id"), NAME, ITEMS, MATERIAL])
def collection_add(ctx, targets, args):
    id_ = args.get("id") or ctx.new_id(K.TYPE)
    refuse_used_id(ctx, id_)
    n = len(K.all_of(ctx.doc)) + 1
    ctx.insert("root", K.LIST, {"id": id_, "type": K.TYPE, "name": args.get("name") or f"Collection {n}",
                                "items": _real(ctx, args.get("items") or []), "material": args.get("material") or ""})


@R.operation("collection.set", "Rename a collection, set its list (`items`), add to it (`include`), take out "
             "(`exclude`) or set its material rule.", target=K.TYPE, label="Edit collection",
             params=[NAME, ITEMS, INCLUDE, EXCLUDE, MATERIAL])
def collection_set(ctx, targets, args):
    for t in targets:
        c = ctx.item(t)
        items = list(args["items"]) if "items" in args else list(c.get("items", []))
        items += [i for i in args.get("include", []) if i not in items]
        items = _real(ctx, [i for i in items if i not in set(args.get("exclude", []))])
        if items != c.get("items", []):
            ctx.set(t, "items", items)
        for k in ("name", "material"):
            if k in args:
                ctx.set(t, k, args[k])


@R.operation("collection.remove", "Delete collections (their items stay). A light that named one lights only what "
             "else it names (everything if nothing else).", target=K.TYPE, label="Delete", importance="secondary")
def collection_remove(ctx, targets, args):
    gone = set(targets)
    for it in [i for i in K._items(ctx.doc) if i.get("type") == "light"]:
        words = it.get("lightsOnly", "").split()
        if gone & set(words):
            ctx.set(it["id"], "lightsOnly", " ".join(w for w in words if w not in gone))
    for t in targets:
        ctx.remove(t)


@R.operation("collection.material", "Give every member of a collection that can wear a material that material.",
             target=K.TYPE, label="Give material",
             params=[Param.text("material", label="Material", required=True, help='A material id, or "" for none')])
def collection_material(ctx, targets, args):
    if args["material"] and ctx.item(args["material"]).get("type") != "material":
        ctx.fail(codes.BAD_ARGUMENT, f'material "{args["material"]}"', "is not a material")
    for t in targets:
        for m in K.members(ctx.doc, ctx.item(t)):
            if ctx.item(m).get("type") in K.USERS:
                ctx.set(m, "material", args["material"])


@R.operation("collection.show", "Show or hide every member of a collection: in every shot, or in one `shot` only.",
             target=K.TYPE, label="Show / hide",
             params=[Param.toggle("visible", label="Visible", required=True),
                     Param.text("shot", label="Only in shot", help="A shot id: shown / hidden in that shot only")])
def collection_show(ctx, targets, args):
    shot = args.get("shot") or ""
    if shot and shot not in {s["id"] for s in ctx.doc.get("shots", [])}:
        ctx.fail(codes.BAD_ARGUMENT, f'shot "{shot}"', "is not a shot")
    for t in targets:
        for m in K.members(ctx.doc, ctx.item(t)):
            if shot:
                own = L.of(ctx.item(shot))
                ctx.set(shot, L.FIELD, {**own, m: {**own.get(m, {}), "visible": bool(args["visible"])}})
            else:
                ctx.set(m, "visible", bool(args["visible"]))
