"""Operations that add, remove, rename and arrange compositions, layers, effects and masks. Field changes are
the generated `<type>.set` operations (kind.py); keys are in ops_keys.py.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import fields as F
from .kind import LISTS, REGISTRY as R
from .names import display_name, unique_name

ID = Param.text("id", label="Id", help="Optional; counted per type when left out (text_1, text_2 …)")
NAME = Param.text("name", label="Name")
INDEX = Param.number("index", label="Position", min=0, max=100000, integer=True, importance="deep",
                     help="Place in the list (0 = bottom of the stack); end when left out")
LAYER_HOLDERS = ("comp", "group", "rig")


def new_item(ctx, type_, args, **extra) -> dict:
    id_ = args.get("id") or ctx.new_id(type_)
    if id_ in _all_ids(ctx):
        ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
    name = args.get("name") or (unique_name(_names(ctx), F.LABELS[type_])
                                if type_ in F.LAYERS else F.LABELS[type_])
    item = {"id": id_, "type": type_, "name": name, **F.defaults(type_), **extra}
    for key in LISTS.get(type_, []):
        item[key] = []
    return item


def _all_ids(ctx):
    from rostrum_core.tree import index
    return index(ctx.doc, ctx.kind.lists)


def _names(ctx) -> set[str]:
    """The names a person reads in the layers list (a layer named only "Text" with a meaningful id shows its id, so
    it doesn't take the name "Text" from the next new text)."""
    return {display_name(loc.item) for loc in _all_ids(ctx).values() if loc.item.get("type") != "doc"}


@R.operation("comp.add", "Add a composition (one shot: its frame size, frame rate and length).", label="Add composition",
             params=[ID, NAME, *F.FIELDS["comp"]])
def comp_add(ctx, targets, args):
    item = new_item(ctx, "comp", args)
    item.update({k: v for k, v in args.items() if k not in ("id", "name")})
    ctx.insert("root", "comps", item)


@R.operation("comp.remove", "Delete compositions with everything in them. Never the last one.",
             target=("comp",), label="Delete composition", importance="secondary")
def comp_remove(ctx, targets, args):
    comps = ctx.doc.get("comps", [])
    left = [c["id"] for c in comps if c["id"] not in targets]
    if not left:
        ctx.fail(codes.BAD_ARGUMENT, "the composition(s) " + ", ".join(f'"{t}"' for t in targets),
                 "would leave the document with no composition", hint="Add the new one first (comp.add), then remove the old.")
    for t in targets:
        ctx.remove(t)


@R.operation("layer.add", "Add a shape, text, image, group or drawing to a composition or group (on top unless index is given).",
             target=LAYER_HOLDERS, label="Add layer",
             params=[Param.choice("type", list(F.LAYERS), label="Type", required=True), ID, NAME, INDEX])
def layer_add(ctx, targets, args):
    from .ops_draw import starter_frame
    for t in targets:
        item = new_item(ctx, args["type"], args if len(targets) == 1 else {**args, "id": None})
        ctx.insert(t, "layers", item, args.get("index"))
        if item["type"] == "drawing":            # a new drawing starts with one drawing at frame 0, ready to paint
            ctx.insert(item["id"], "frames", starter_frame(ctx))


@R.operation("layer.remove", "Delete layers (with their effects, masks and keys).", target=F.LAYERS, label="Delete",
             importance="secondary")
def layer_remove(ctx, targets, args):
    from .rig.ops import drop_binds
    drop_binds(ctx, targets)
    for t in targets:
        ctx.remove(t)


@R.operation("layer.duplicate", "Copy layers: each copy lands just above its original, named \"<name> copy\", with its keys, "
             "effects, masks and layers inside it copied under new ids.", target=F.LAYERS, label="Duplicate",
             importance="secondary")
def layer_duplicate(ctx, targets, args):
    from rostrum_core import ids
    from rostrum_core.tree import bare, child_keys
    lists = ctx.kind.lists

    def put(item, parent, key, at, taken):
        new = {**bare(item, lists), "id": ids.counted(taken, item["type"])}
        taken.add(new["id"])
        ctx.insert(parent, key, new, at)
        for k in child_keys(item, lists):
            for child in item.get(k, []):
                put(child, new["id"], k, None, taken)
        return new["id"]

    for t in targets:
        idx = _all_ids(ctx)
        loc = idx[t]
        copy = put(loc.item, loc.parent, loc.key, loc.index + 1, set(idx))
        ctx.set(copy, "name", unique_name(_names(ctx), f"{display_name(loc.item)} copy"))


@R.operation("item.rename", "Rename a composition, layer, effect, mask or a rig's saved pose.",
             target=("comp", *F.LAYERS, *F.EFFECTS, "mask", "pose"),
             label="Rename", params=[Param.text("name", label="Name", required=True)], importance="secondary")
def item_rename(ctx, targets, args):
    for t in targets:
        ctx.set(t, "name", args["name"])


@R.operation("layer.arrange", "Move a layer in the stack, or into another group or composition.", target=F.LAYERS,
             label="Arrange", importance="secondary",
             params=[Param.id("into", label="Into", help="A group or composition; the layer's own when left out"),
                     Param.number("index", label="Position", min=0, max=100000, integer=True, required=True,
                                  help="0 = bottom of the stack")])
def layer_arrange(ctx, targets, args):
    from rostrum_core.tree import index
    from .rig.ops import drop_binds
    for t in targets:
        loc = index(ctx.doc, ctx.kind.lists)[t]
        into = args.get("into") or loc.parent
        holder = ctx.item(into)
        if holder["type"] not in LAYER_HOLDERS:
            ctx.fail(codes.BAD_ARGUMENT, f'into "{into}"', f"is a {holder['type']}, not a group or composition")
        if t == into or into in _descendants(ctx, t):
            ctx.fail(codes.BAD_ARGUMENT, f'into "{into}"', "is the layer itself or inside it")
        if into != loc.parent:
            drop_binds(ctx, [t])           # a layer leaving its rig leaves its bind behind
        ctx.move(t, into, "layers", args["index"])


def _descendants(ctx, id_):
    from rostrum_core.tree import subtree_ids
    return subtree_ids(ctx.item(id_), ctx.kind.lists)


@R.operation("effect.add", "Add an effect to layers: blur, glow, gradient (fills a shape, or a text's letters), shadow, frosted glass, "
             "grain (film grain on the layer's own look; on a group it covers all its layers), trail, smear.",
             target=F.LAYERS, label="Add effect",
             params=[Param.choice("type", list(F.EFFECTS), label="Effect", required=True), ID, NAME, INDEX])
def effect_add(ctx, targets, args):
    for t in targets:
        ctx.insert(t, "effects", new_item(ctx, args["type"], args if len(targets) == 1 else {**args, "id": None}),
                   args.get("index"))


@R.operation("mask.add", "Add a mask to layers: only the part inside it shows (or outside, inverted).",
             target=F.LAYERS, label="Add mask", params=[ID, NAME])
def mask_add(ctx, targets, args):
    for t in targets:
        ctx.insert(t, "masks", new_item(ctx, "mask", args if len(targets) == 1 else {**args, "id": None}))


@R.operation("effect.remove", "Delete effects or masks.", target=(*F.EFFECTS, "mask"), label="Delete",
             importance="secondary")
def effect_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)

