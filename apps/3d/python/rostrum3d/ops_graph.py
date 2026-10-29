"""The blocks graph's operations (brief 23): graph.add, graph.connect, graph.set, graph.remove on a material. Each is
one undo step (one call: the graph written back whole, plus the material fields a Surface or stylized block changes)
and fails loudly with what was wrong and what is accepted. The data and the rules are graph.py; the catalogue
graph_blocks.py. Read a graph with graph.describe(material) (the screen, look_material).
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import graph as G
from . import graph_blocks as B
from .kind import REGISTRY as R

XY = [Param.number("x", label="X", min=-1e5, max=1e5, help="Where the block sits in the Blocks view (screen units)"),
      Param.number("y", label="Y", min=-1e5, max=1e5)]
VALUES = B.Values("values", "text", label="Settings",
                  help="{setting: value} by the block type's settings (graph.describe's catalogue lists them)")


def _fail(ctx, e: G.GraphError):
    ctx.fail(codes.BAD_ARGUMENT, e.subject, e.problem, e.accepted, e.hint)


def _material_values(ctx, mid: str, vals: dict, names) -> None:
    """Surface / stylized block values = the material's own fields, checked by material.set's params."""
    op = R.get("material.set")
    for k, v in vals.items():
        if k not in names:
            ctx.fail(codes.BAD_ARGUMENT, f'"{k}"', "is not a setting of this block", sorted(names))
        ctx.set(mid, k, op.param(k).check(v, ctx.where))


def _write(ctx, mid: str, g: dict) -> None:
    """The graph back on the material, and the stylized switches it implies (wired into Style = on)."""
    ctx.set(mid, G.FIELD, g)
    for toggle, on in G.toggles(g).items():
        ctx.set(mid, toggle, on)


def _one(ctx, targets):
    if len(targets) != 1:
        ctx.fail(codes.BAD_ARGUMENT, f"target {targets}", "must be one material")
    return targets[0], ctx.item(targets[0])


@R.operation("graph.add", "Add a block to a material's Blocks view (its graph): `type` one of image, noise, pattern, mix, ramp, "
             "curve, colourAdjust, bevel, occlusion, lines, lightToColour, halftone; optional `id` (else <type>_<n>), "
             "`x`, `y` and `values` ({setting: value}, the type's settings: graph.describe's catalogue). A Lines, "
             "Light to colour or Halftone block's settings are the material's own fields; it switches on when wired "
             "into Surface's style (graph.connect). Returns the block.",
             target="material", label="Add block", importance="secondary",
             params=[Param.choice("type", list(B.BY_TYPE), label="Block", required=True,
                                  labels={b.type: b.label for b in B.BLOCKS}),
                     Param.text("id", label="Id", help="Letters, digits and single _; else <type>_<n>"), *XY, VALUES])
def graph_add(ctx, targets, args):
    mid, mat = _one(ctx, targets)
    g, type_ = G.graph_of(mat), args["type"]
    taken = set(G.blocks_by_id(g)) | {G.SURFACE}
    bid = args.get("id") or next(f"{type_}_{n}" for n in range(1, 10**6) if f"{type_}_{n}" not in taken)
    if bid in taken or not G.BLOCK_ID.match(bid):
        ctx.fail(codes.BAD_ARGUMENT, f'id "{bid}"', "is taken" if bid in taken else "is not letters, digits and single _",
                 hint="Leave id out for a new one.")
    if type_ in B.STYLIZED and any(b["type"] == type_ for b in g["blocks"]):
        ctx.fail(codes.BAD_ARGUMENT, f'type "{type_}"', "is already in this material (one per material: its settings "
                 "are the material's own)", hint="Change the one there with graph.set.")
    block = {"id": bid, "type": type_, "x": args.get("x", 0), "y": args.get("y", 0)}
    vals = args.get("values") or {}
    if type_ in B.STYLIZED:
        _material_values(ctx, mid, vals, {i.name for i in B.BY_TYPE[type_].inputs if i.name != B.CHAIN})
    else:
        try:
            block["values"] = {k: G.check_value(type_, k, v, ctx.where) for k, v in vals.items()}
        except G.GraphError as e:
            _fail(ctx, e)
    g["blocks"].append(block)
    _write(ctx, mid, g)
    return block


@R.operation("graph.connect", 'Wire a block\'s output into an input: `from` "block.output" (e.g. "noise_1.value"), '
             '`to` "block.input" (e.g. "surface.roughness"; Surface\'s inputs: baseColor, roughness, metallic, '
             "emissionColor, normal, style). Replaces the input's old wire. Colour and number join either way "
             "(a number as grey, a colour as its brightness); normal and style only their own kind; no loops.",
             target="material", label="Wire", importance="secondary",
             params=[Param.text("from", label="From", required=True, help='"block.output"'),
                     Param.text("to", label="To", required=True, help='"block.input"')])
def graph_connect(ctx, targets, args):
    mid, mat = _one(ctx, targets)
    g = G.graph_of(mat)
    try:
        G.check_wire(g, args["from"], args["to"])
    except G.GraphError as e:
        _fail(ctx, e)
    g["wires"] = [w for w in g["wires"] if w["to"] != args["to"]] + [{"from": args["from"], "to": args["to"]}]
    _write(ctx, mid, g)
    return {"from": args["from"], "to": args["to"]}


SHOW = [Param.list("show", "text", label="Show on the material",
                   help="Settings of this block to show as plain rows in the material's own settings (e.g. a Noise's "
                        "scale), so it can be changed without opening the blocks"),
        Param.list("hide", "text", label="Hide from the material", help="Settings shown there to take away again")]


@R.operation("graph.set", "Change a block: `block` its id, then `values` ({setting: value}) and / or `x`, `y` (its "
             'place in the view). `block: "surface"` changes the material\'s own fields (as material.set) or Surface\'s '
             "place. `show` / `hide` [settings]: a block's settings shown as plain rows in the material's own settings "
             '("Noise · Scale"), so a person or agent changes them there without opening the blocks.',
             target="material", label="Change block", importance="secondary",
             params=[Param.text("block", label="Block", required=True), VALUES, *XY, *SHOW])
def graph_set(ctx, targets, args):
    mid, mat = _one(ctx, targets)
    g, bid = G.graph_of(mat), args["block"]
    try:
        kind = G.type_of(g, bid, "block")
    except G.GraphError as e:
        _fail(ctx, e)
    vals = args.get("values") or {}
    place = g["surface"] if bid == G.SURFACE else G.blocks_by_id(g)[bid]
    for k in ("x", "y"):
        if k in args:
            place[k] = args[k]
    if kind.type == "surface" or kind.type in B.STYLIZED:
        names = {p.name for p in R.get("material.set").params} if kind.type == "surface" else \
            {i.name for i in kind.inputs if i.name != B.CHAIN}
        _material_values(ctx, mid, vals, names)
    else:
        try:
            place["values"] = {**place.get("values", {}),
                               **{k: G.check_value(kind.type, k, v, ctx.where) for k, v in vals.items()}}
        except G.GraphError as e:
            _fail(ctx, e)
    if args.get("show") or args.get("hide"):
        can = G.showable(kind)
        for name in [*args.get("show", []), *args.get("hide", [])]:
            if name not in can:
                ctx.fail(codes.BAD_ARGUMENT, f'"{name}"', f"is not a setting {kind.label} can show on the material",
                         can, hint="Surface's and stylized blocks' settings are the material's own rows already."
                         if not can else None)
        now = [n for n in can if n in set(place.get("shown") or ()) | set(args.get("show", []))
               and n not in set(args.get("hide", []))]
        if now:
            place["shown"] = now
        else:
            place.pop("shown", None)
    if "x" in args or "y" in args or args.get("show") or args.get("hide") or             (vals and kind.type not in ("surface", *B.STYLIZED)):
        ctx.set(mid, G.FIELD, g)
    return {"block": bid}


@R.operation("graph.remove", 'Take blocks and / or wires out of a material\'s Blocks view: `blocks` [ids] (their '
             'wires go too; Surface stays), `wires` [inputs "block.input" whose wire goes]. A Lines, Light to colour or '
             "Halftone block taken out (or its wire) switches that setting off.",
             target="material", label="Remove blocks", importance="secondary",
             params=[Param.list("blocks", "text", label="Blocks"), Param.list("wires", "text", label="Wires")])
def graph_remove(ctx, targets, args):
    mid, mat = _one(ctx, targets)
    g = G.graph_of(mat)
    ids, ins, have = set(args.get("blocks") or []), set(args.get("wires") or []), G.blocks_by_id(g)
    if not ids and not ins:
        ctx.fail(codes.BAD_ARGUMENT, "blocks / wires", "are both empty", hint="Name the blocks or the wires' inputs.")
    for bid in ids:
        if bid not in have:
            ctx.fail(codes.NOT_FOUND, f'block "{bid}"', "is not a block of this material" +
                     (" (Surface is the material itself: it stays)" if bid == G.SURFACE else ""), sorted(have))
    linked = G.wires_into(g)
    for to in ins:
        if to not in linked:
            ctx.fail(codes.NOT_FOUND, f'wire into "{to}"', "is not there", sorted(linked))
    off = {B.STYLIZED[have[b]["type"]] for b in ids if have[b]["type"] in B.STYLIZED}
    g["blocks"] = [b for b in g["blocks"] if b["id"] not in ids]
    g["wires"] = [w for w in g["wires"] if w["to"] not in ins and w["from"].split(".")[0] not in ids
                  and w["to"].split(".")[0] not in ids]
    _write(ctx, mid, g)
    for toggle in off:
        ctx.set(mid, toggle, False)
    return {"removed": sorted(ids), "unwired": sorted(ins)}
