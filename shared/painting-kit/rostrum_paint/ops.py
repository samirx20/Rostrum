"""The painting kit's operations, registered on a host app's registry: paint layers, strokes and masks are items in
the app's one document, so painting goes through the one door (`Document.apply`) and the one history.

    register(REGISTRY, canvas_types=("frame",))

**A stroke batch is one call list**: `doc.apply([stroke.add, stroke.add, …], who)` is one change = one undo step,
recorded with who painted it. A live pen stroke is one gesture: `stroke.add` once, then `stroke.set {points}`.
"""
from __future__ import annotations

import zlib

from rostrum_core import Param
from rostrum_core.errors import RostrumError, codes, did_you_mean
from rostrum_core.tree import index

from . import fields as F

ID = Param.text("id", label="Id", importance="deep", help="Optional; counted per type when left out (stroke_1 …)")
INDEX = Param.number("index", label="Position", min=0, max=100000, integer=True, importance="deep",
                     help="Place in the list (0 = bottom); on top when left out")


def seed_of(stroke_id: str) -> int:
    """A stroke's seed when none is given: from its id, so the same script paints the same bristles every run."""
    return zlib.crc32(stroke_id.encode("utf-8")) & 0x7FFFFFFF


def build(type_: str, id_: str, values: dict, where: str = "") -> dict:
    """A new kit item from checked values, defaults filled in: the one builder, used by the operations and by an
    app's script layer, so a scripted stroke and a painted one are the same item. Every brush setting is stored
    (and the seed fixed), so the stroke replays the same even if a default changes later."""
    params = {p.name: p for p in F.FIELDS[type_]}
    for k in values:
        if k not in params:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'"{k}"', f"is not a field of a {F.LABELS[type_].lower()}",
                               sorted(params), did_you_mean(k, params))
    item = {"id": id_, "type": type_, **F.defaults(type_),
            **{k: params[k].check(v, where) for k, v in values.items()}}
    for key in F.LISTS[type_]:
        item[key] = []
    if type_ == "stroke":
        if "points" not in item:
            raise RostrumError(codes.BAD_ARGUMENT, where, '"points"', "is required", ["[[x, y, pressure], …]"])
        item["points"] = with_pressure(item["points"])
        if "seed" not in values:
            item["seed"] = seed_of(id_)
    return item


def with_pressure(points) -> list:
    return [list(q) if len(q) > 2 else [*q, 1.0] for q in points]


def _new(ctx, type_, args) -> dict:
    id_ = args.get("id") or ctx.new_id(type_)
    if id_ in index(ctx.doc, ctx.kind.lists):
        ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
    return build(type_, id_, {k: v for k, v in args.items() if k not in ("id", "index")}, ctx.where)


def canvas_of(doc_data, kind_lists, item_id) -> dict:
    """The canvas (host item) a paint layer, stroke or paint mask belongs to."""
    idx = index(doc_data, kind_lists)
    loc = idx[item_id]
    while loc.key not in F.CANVAS_LISTS:
        loc = idx[loc.parent]
    return idx[loc.parent].item


def _check_mask(ctx, paint_or_stroke_id, mask_id, where_id):
    if not mask_id:
        return
    canvas = canvas_of(ctx.doc, ctx.kind.lists, paint_or_stroke_id)
    names = [m["id"] for m in canvas.get("paintmasks", [])]
    if mask_id not in names:
        ctx.fail(codes.NOT_FOUND, f'mask "{mask_id}"', f"is not a paint mask of {canvas['id']} (for {where_id})",
                 names)


def register(registry, canvas_types=("frame",)):
    """Add the kit's operations to an app's registry. `canvas_types`: the host item types that are canvases."""
    canvas_types = tuple(canvas_types)
    for type_ in ("paint", "stroke", "paintmask"):
        _field_op(registry, type_)

    @registry.operation("paint.add", "Add a paint layer to a canvas (on top unless index is given).", target=canvas_types,
                        label="Add paint layer", params=[ID, *F.FIELDS["paint"], INDEX])
    def paint_add(ctx, targets, args):
        for t in targets:
            ctx.insert(t, "paints", _new(ctx, "paint", args if len(targets) == 1 else {**args, "id": None}),
                       args.get("index"))

    @registry.operation("paint.clear", "Remove every stroke of paint layers (to redraw them).", target="paint",
                        label="Clear paint", importance="secondary")
    def paint_clear(ctx, targets, args):
        for t in targets:
            for s in list(ctx.item(t)["strokes"]):
                ctx.remove(s["id"])

    @registry.operation("paint.unlock", "Unlock paint layers so they take paint again.", target="paint",
                        label="Unlock", importance="secondary", valid_when={"is": ["locked", True]})
    def paint_unlock(ctx, targets, args):
        for t in targets:
            ctx.set(t, "locked", False)

    @registry.operation("stroke.add", "Paint one stroke into a paint layer: a path of points and a brush. Several "
                        "stroke.add calls in one call list are one undo step.", target="paint", label="Paint",
                        params=[ID, *(_required(p) if p.name == "points" else p for p in F.FIELDS["stroke"])])
    def stroke_add(ctx, targets, args):
        for t in targets:
            item = _new(ctx, "stroke", args if len(targets) == 1 else {**args, "id": None})
            _check_mask(ctx, t, item["mask"], item["id"])
            ctx.insert(t, "strokes", item)

    @registry.operation("stroke.remove", "Delete strokes.", target="stroke", label="Delete stroke",
                        importance="secondary")
    def stroke_remove(ctx, targets, args):
        for t in targets:
            ctx.remove(t)

    @registry.operation("paintmask.add", "Add a paint mask (a polygon) to a canvas; strokes name it to paint only "
                        "inside it (or outside, inverted).", target=canvas_types, label="Add paint mask",
                        params=[ID, *(_required(p) if p.name == "points" else p for p in F.FIELDS["paintmask"])])
    def paintmask_add(ctx, targets, args):
        for t in targets:
            ctx.insert(t, "paintmasks", _new(ctx, "paintmask", args if len(targets) == 1 else {**args, "id": None}))


def _required(p: Param) -> Param:
    from dataclasses import replace
    return replace(p, required=True)


def _field_op(registry, type_):
    def set_fields(ctx, targets, args):
        for t in targets:
            for k, v in args.items():
                if k == "points" and type_ == "stroke":
                    v = with_pressure(v)
                if k == "mask":
                    _check_mask(ctx, t, v, t)
                ctx.set(t, k, v)
    label = F.LABELS[type_].lower()
    registry.operation(f"{type_}.set", f"Change a {label}'s settings.", target=type_, params=F.FIELDS[type_],
                       label=f"Edit {label}", fields=True)(set_fields)
