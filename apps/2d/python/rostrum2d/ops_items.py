"""Operations that add, remove, rename and arrange compositions, layers, effects and masks. Field changes are
the generated `<type>.set` operations (kind.py); keys are in ops_keys.py.
"""
from __future__ import annotations

import re

from rostrum_core import PLUGIN_ITEM, Param
from rostrum_core.errors import codes

from . import fields as F
from .kind import LISTS, REGISTRY as R
from .names import copy_base, display_name, unique_name
from .ops_vary import PARAMS as VARY, draw, vary, wanted

ID = Param.text("id", label="Id", help="Optional; counted per type when left out (text_1, text_2 …)")
NAME = Param.text("name", label="Name")
INDEX = Param.number("index", label="Position", min=0, max=100000, integer=True, importance="deep",
                     help="Place in the list (0 = bottom of the stack); end when left out")
LAYER_HOLDERS = ("comp", "group", "rig")


def new_item(ctx, type_, args, **extra) -> dict:
    id_ = args.get("id") or ctx.new_id(type_)
    if id_ in _all_ids(ctx):
        ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
    name = args.get("name") or (scene_name(ctx) if type_ == "comp" else unique_name(_names(ctx), F.LABELS[type_])
                                if type_ in F.LAYERS else F.LABELS[type_])
    item = {"id": id_, "type": type_, "name": name, **F.defaults(type_), **extra}
    for key in LISTS.get(type_, []):
        item[key] = []
    return item


def scene_name(ctx) -> str:
    """A new scene is numbered: "Scene 2", then "Scene 3" (the first scene is the project's own, "Main" or the like)."""
    taken, n = _names(ctx), 2
    if not ctx.doc.get("comps"):
        return F.LABELS["comp"]
    while f"{F.LABELS['comp']} {n}" in taken:
        n += 1
    return f"{F.LABELS['comp']} {n}"


def _all_ids(ctx):
    from rostrum_core.tree import index
    return index(ctx.doc, ctx.kind.lists)


def _names(ctx) -> set[str]:
    """The names a person reads in the layers list (a layer named only "Text" with a meaningful id shows its id, so
    it doesn't take the name "Text" from the next new text)."""
    items = [loc.item for loc in _all_ids(ctx).values() if loc.item.get("type") != "doc"]
    return {display_name(i) for i in items} | {i["name"] for i in items if i.get("name")}     # a star named "Shape" still holds that name


@R.operation("comp.add", "Add a composition (one shot: its frame size, frame rate and length). It comes with its frame "
             "(the box that is exported) at home, still.", label="New scene",
             params=[ID, NAME, *F.FIELDS["comp"]])
def comp_add(ctx, targets, args):
    from .frame import make
    item = new_item(ctx, "comp", args)
    item.update({k: v for k, v in args.items() if k not in ("id", "name")})
    ctx.insert("root", "comps", item)
    ctx.insert(item["id"], "layers", make.new(item, {*_all_ids(ctx), item["id"]}))


@R.operation("comp.remove", "Delete scenes with everything in them (Undo brings them back). Never the last one.",
             target=("comp",), label="Delete scene", importance="secondary")
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
             params=[Param.choice("type", list(F.PLACED), label="Type", required=True), ID, NAME, INDEX,
                     Param.number("frame", label="First drawing at frame", min=0, max=10**7, integer=True, importance="deep",
                                  help="A drawing layer: the frame its first drawing starts at (default 0). Give it with "
                                       "eachFrame on to start a frame-by-frame run at the playhead")])
def layer_add(ctx, targets, args):
    from .ops_draw import starter_frame
    if "frame" in args and args["type"] != "drawing":
        ctx.fail(codes.BAD_ARGUMENT, '"frame"', f'only a drawing layer has a first drawing: a {args["type"]} has none',
                 hint="Leave frame out, or add a drawing layer.")
    for t in targets:
        item = new_item(ctx, args["type"], args if len(targets) == 1 else {**args, "id": None})
        ctx.insert(t, "layers", item, args.get("index"))
        if item["type"] == "drawing":            # a new drawing starts with one drawing at frame 0, ready to paint
            ctx.insert(item["id"], "frames", starter_frame(ctx, args.get("frame", 0)))


@R.operation("layer.remove", "Delete layers (with their effects, masks and keys). Never a scene's frame.", target=(*F.LAYERS, PLUGIN_ITEM),
             label="Delete", importance="secondary")    # the frame is a target so screens can pick it (layer_order.py)
def layer_remove(ctx, targets, args):
    from .rig.ops import drop_binds
    for t in targets:
        if ctx.item(t)["type"] == "camera":
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', "is the scene's frame (what is exported); it can't be deleted",
                     hint="Move it home instead (its X, Y at Home X, Home Y), or lock it.")
    drop_binds(ctx, targets)
    for t in targets:
        ctx.remove(t)


def _by(name, label, unit, **kw):
    return Param.number(name, label=label, unit=unit, min=-100000, max=100000, importance="secondary", **kw)


@R.operation("layer.duplicate", "Copy layers: each copy lands just above its original in the stack, named \"<name> copy\" (a text that reads as its words keeps doing so), "
             "with its keys, effects, masks and layers inside it copied under new ids. Without `by_x` / `by_y` / `by_turn` / "
             "`by_scale` it is nudged 24 px right and down (further for each more copy, so none sits exactly on another). "
             "With them, `times` copies (1 to 200) each take that step from the one before, as one change: "
             "{by_x: 240, times: 7} makes a row of eight. `by_scale` is a factor (1.1 = a tenth bigger each). `copy_ids` names "
             "the copies: \"icon_{n}\" gives icon_1, icon_2 … (n counts from 1, up the stack from the original), as id and name. "
             "Varied copies (no clones): give `vary_scale` (0.25 = 75-125 %), `vary_turn` (±°), `vary_move` (±px), `vary_hue` (±°), `vary_light` (±), "
             "`vary_opacity` (±) and/or `vary_time` (±s: when its animation starts) with a `seed`: each copy gets its own random amounts "
             "within those ranges (same seed, same copies); every copy is then an ordinary layer you can edit.",
             target=F.PLACED, label="Duplicate", importance="secondary",
             params=[_by("by_x", "Step across", "px"), _by("by_y", "Step down", "px"), _by("by_turn", "Step turn", "°"),
                     Param.number("by_scale", label="Step scale", unit="×", min=0.01, max=100, importance="secondary"),
                     Param.number("times", label="Copies", min=1, max=200, integer=True, default=1, importance="secondary",
                                  help="How many copies, each one step on from the last"),
                     Param.text("copy_ids", label="Copy ids", importance="deep",
                                help='Ids for the copies, {n} the number of each: "icon_{n}"'), *VARY])
def layer_duplicate(ctx, targets, args):
    from rostrum_core import ids
    from rostrum_core.tree import bare, child_keys
    lists = ctx.kind.lists

    pattern = args.get("copy_ids")
    if pattern is not None and ("{n}" not in pattern or len(targets) > 1):
        ctx.fail(codes.BAD_ARGUMENT, "copy_ids", f'"{pattern}" names the copies of one layer and holds {{n}}, the number of each copy',
                 ['"icon_{n}"'], hint="Duplicate one layer at a time to name its copies.")

    def put(item, parent, key, at, taken, step=0, id_=None, varied=None):
        if id_ is not None and (id_ in taken or not ids.is_valid(id_)):
            ctx.fail(codes.BAD_ARGUMENT, "copy_ids", f'"{id_}" is already in the document or not a usable id (letters, digits, '
                     "_ . -; not starting with a digit)", hint="Pick another pattern, e.g. a word no layer uses yet.")
        new = stepped({**bare(item, lists), "id": id_ or ids.counted(taken, item["type"], start=after.get(item["type"], 1))}, step)
        if varied:
            vary(new, varied)
        taken.add(new["id"])
        if id_ is None:                             # the next counted id of this type starts after it (copies of 200)
            after[item["type"]] = int(new["id"].rsplit("_", 1)[1]) + 1
        ctx.insert(parent, key, new, at)
        for k in child_keys(item, lists):
            for child in item.get(k, []):
                put(child, new["id"], k, None, taken, for_child(child, step), varied=varied if child.get("type") == "key" else None)
        return new["id"]

    from .ops_nudge import NUDGE, for_child, spots, steps_for, stepped
    by = [args.get(k) for k in ("by_x", "by_y", "by_turn", "by_scale")]
    given = any(v is not None for v in by)
    dx, dy, turn, ratio = (by[0] or 0, by[1] or 0, by[2] or 0, by[3] if by[3] is not None else 1)
    ranges = wanted(args)
    if "seed" in args and not ranges:
        ctx.fail(codes.BAD_ARGUMENT, '"seed"', "varies nothing without a range", ["vary_scale", "vary_turn", "vary_move", "vary_hue", "vary_light", "vary_opacity", "vary_time"],
                 hint="Give at least one vary_ range with the seed.")
    taken, names, after = set(ctx.idx), _names(ctx), {}   # once per call, then kept up to date: copying 200 layers
    places = {}                                     # was 600 walks of the whole document (~2 s in an Alt+drag)
    for t in targets:
        loc = ctx.idx[t]                            # (its parent and list hold; its position may be stale)
        siblings = ctx.item(loc.parent).get(loc.key, [])
        if not given:                               # where its siblings and the copies so far sit (ops_nudge.py)
            place = places.get((loc.parent, loc.key))
            if place is None:
                place = places[(loc.parent, loc.key)] = spots(siblings)
            first = steps_for(siblings, [loc.item], place)
        at = next(i for i, c in enumerate(siblings) if c is loc.item) + 1
        name = copy_base(loc.item)        # "<name> copy" ("copy 2", never "copy copy"); a text named by its words keeps following them
        for n in range(1, args.get("times", 1) + 1):
            step = (n * dx, n * dy, n * turn, ratio ** n) if given else first + n - 1
            copy = put(loc.item, loc.parent, loc.key, at, taken, step, pattern and pattern.replace("{n}", str(n)),
                       draw(ranges, args.get("seed", 1), f"{t}|{n}") if ranges else None)
            named = copy if pattern else unique_name(names, name)
            names.add(named)
            ctx.set(copy, "name", named)
            if not given:
                place |= spots([ctx.item(copy)])
            at += 1


@R.operation("item.rename", "Rename a composition, layer, effect, mask or a rig's saved pose.",
             target=("comp", *F.PLACED, *F.EFFECTS, "mask", "pose"),
             label="Rename", params=[Param.text("name", label="Name", required=True)], importance="secondary")
def item_rename(ctx, targets, args):
    for t in targets:
        ctx.set(t, "name", args["name"])


@R.operation("layer.arrange", "Move a layer in the stack, or into another group or composition.", target=(*F.PLACED, PLUGIN_ITEM),
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
             "grain (film grain on the layer's own look; on a group it covers all its layers), rough (edges wobble as if drawn by "
             "hand: amount px, size px of a bump, detail, boil frames), trail, smear.",
             target=F.PLACED, label="Add effect",
             params=[Param.choice("type", list(F.EFFECTS), label="Effect", required=True), ID, NAME, INDEX])
def effect_add(ctx, targets, args):
    for t in targets:
        ctx.insert(t, "effects", new_item(ctx, args["type"], args if len(targets) == 1 else {**args, "id": None}),
                   args.get("index"))


@R.operation("mask.add", "Add a mask to layers: only the part inside it shows (or outside, inverted).",
             target=F.PLACED, label="Add mask", params=[ID, NAME])
def mask_add(ctx, targets, args):
    for t in targets:
        ctx.insert(t, "masks", new_item(ctx, "mask", args if len(targets) == 1 else {**args, "id": None}))


@R.operation("effect.remove", "Delete effects or masks.", target=(*F.EFFECTS, "mask"), label="Delete",
             importance="secondary")
def effect_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)

