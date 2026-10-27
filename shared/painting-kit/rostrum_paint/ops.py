"""The painting kit's operations, registered on a host app's registry: paint layers, strokes and masks are items in
the app's one document, so painting goes through the one door (`Document.apply`) and the one history.

    register(REGISTRY, canvas_types=("frame",))

**A stroke batch is one call list**: `doc.apply([stroke.add, stroke.add, …], who)` is one change = one undo step,
recorded with who painted it. A live pen stroke is one gesture: `stroke.add` once, then `stroke.set {points}`.
"""
from __future__ import annotations

import zlib
from copy import deepcopy as copy_item

from rostrum_core import Param
from rostrum_core.errors import RostrumError, codes, did_you_mean
from rostrum_core.tree import index

from . import fields as F, linked

ID = Param.text("id", label="Id", importance="deep", help="Optional; counted per type when left out (stroke_1 …)")
INDEX = Param.number("index", label="Position", min=0, max=100000, integer=True, importance="deep",
                     help="Place in the list (0 = bottom); on top when left out")


def seed_of(stroke_id: str) -> int:
    """A stroke's seed when none is given: from its id, so the same script paints the same bristles every run."""
    return zlib.crc32(stroke_id.encode("utf-8")) & 0x7FFFFFFF


def build(type_: str, id_: str, values: dict, where: str = "", extra=()) -> dict:
    """A new kit item from checked values, defaults filled in: the one builder, used by the operations and by an
    app's script layer, so a scripted stroke and a painted one are the same item. Every brush setting is stored
    (and the seed fixed), so the stroke replays the same even if a default changes later. `extra`: the host's own
    fields of this type (a paint layer's `layer_fields`, `register`)."""
    params = {p.name: p for p in [*F.FIELDS[type_], *extra]}
    for k in values:
        if k not in params:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'"{k}"', f"is not a field of a {F.LABELS[type_].lower()}",
                               sorted(params), did_you_mean(k, params))
    item = {"id": id_, "type": type_, **F.defaults(type_), **{p.name: p.default for p in extra if p.default is not None},
            **{k: params[k].check(v, where) for k, v in values.items()}}
    for key in F.LISTS[type_]:
        item[key] = []
    if type_ == "stroke":
        if "points" not in item and not any(p.name in values for p in extra):   # a host's own path (3D: anchors)
            raise RostrumError(codes.BAD_ARGUMENT, where, '"points"', "is required", ["[[x, y, pressure], …]"])
        if "points" in item:
            item["points"] = with_pressure(item["points"])
        if "seed" not in values:
            item["seed"] = seed_of(id_)
    return item


def with_pressure(points) -> list:
    return [list(q) if len(q) > 2 else [*q, 1.0] for q in points]


def _new(ctx, type_, args, extra=()) -> dict:
    id_ = args.get("id") or ctx.new_id(type_)
    if id_ in index(ctx.doc, ctx.kind.lists):
        ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
    return build(type_, id_, {k: v for k, v in args.items() if k not in ("id", "index")}, ctx.where, extra)


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


def _alone(ctx, canvas_id):
    return [canvas_id]


def _never(ctx, canvas):
    return False


def register(registry, canvas_types=("frame",), peers=_alone, layer_fields=(), seamless=_never, stroke_fields=()):
    """Add the kit's operations to an app's registry. `canvas_types`: the host item types that are canvases;
    `peers(ctx, canvas_id)`: the canvases sharing paint layers with it (linked.py), itself included;
    `layer_fields`: the host's own paint layer fields (Params), on paint.add and paint.set (3D: which surface
    channel a layer paints); `seamless(ctx, canvas)`: whether a canvas's opposite edges are joined (2D: a seamless
    painting's; 3D: a texture that repeats), so a stroke made on it gets `wrap` (wrap.py) unless it says;
    `stroke_fields`: the host's own stroke fields, on stroke.add and stroke.set (3D: a clay stroke's `anchors` on
    the surface, from which the host lays its `points`; a stroke given one of them may leave `points` out)."""
    canvas_types, extra, own = tuple(canvas_types), tuple(layer_fields), tuple(stroke_fields)

    def every(ctx, targets):
        """Each target paint layer with its copies in the canvases sharing with it, each once, in order."""
        out = []
        for t in targets:
            out += [c for c in linked.copies(ctx, t, canvas_of(ctx.doc, ctx.kind.lists, t)["id"], peers) if c not in out]
        return out
    _field_op(registry, "paint", every, extra)
    _field_op(registry, "stroke", extra=own)
    for type_ in ("fill", "paintmask"):
        _field_op(registry, type_)

    @registry.operation("paint.add", "Add a paint layer to a canvas (on top unless index is given); where canvases share paint "
                        "layers (the drawings of a Draw each frame layer) an empty copy goes into each of them.", target=canvas_types,
                        label="Add paint layer", params=[ID, *F.FIELDS["paint"], *extra, INDEX])
    def paint_add(ctx, targets, args):
        for t in targets:
            linked.add(ctx, t, _new(ctx, "paint", args if len(targets) == 1 else {**args, "id": None}, extra),
                       args.get("index"), peers)

    @registry.operation("paint.remove", "Delete paint layers with their strokes (in every drawing sharing them).", target="paint",
                        label="Delete paint layer", importance="secondary")
    def paint_remove(ctx, targets, args):
        for t in every(ctx, targets):
            ctx.remove(t)

    @registry.operation("paint.duplicate", "Copy paint layers with all their strokes and fills, each copy just above "
                        "its layer, named \"<name> copy\" (same seeds: it paints the same pixels); in every drawing sharing it, each "
                        "copy with that drawing's own strokes.", target="paint",
                        label="Duplicate paint layer", importance="secondary")
    def paint_duplicate(ctx, targets, args):
        for group in [linked.copies(ctx, t, canvas_of(ctx.doc, ctx.kind.lists, t)["id"], peers) for t in targets]:
            key = None
            for t in group:             # each canvas's copy holds that canvas's own strokes, under one new key
                holder, layer = canvas_of(ctx.doc, ctx.kind.lists, t), ctx.item(t)
                at = next(i for i, p in enumerate(holder["paints"]) if p["id"] == t) + 1
                copy = {**copy_item(layer), "id": ctx.new_id("paint"), "name": f'{layer["name"]} copy', "strokes": []}
                copy.pop("layer", None)
                if key:
                    copy["layer"] = key
                key = key or copy["id"]
                ctx.insert(holder["id"], "paints", copy, at)
            for s in layer["strokes"]:
                ctx.insert(copy["id"], "strokes", {**copy_item(s), "id": ctx.new_id(s["type"])})

    @registry.operation("paint.move", "Move a paint layer up or down among its canvas's paint layers (0 = bottom), in every "
                        "drawing sharing it.",
                        target="paint", label="Reorder paint layer", importance="secondary",
                        params=[_required(INDEX)])
    def paint_move(ctx, targets, args):
        for t in every(ctx, targets):
            holder = canvas_of(ctx.doc, ctx.kind.lists, t)
            ctx.move(t, holder["id"], "paints", min(args["index"], len(holder["paints"]) - 1))

    @registry.operation("paint.clear", "Remove every stroke of paint layers (to redraw them).", target="paint",
                        label="Clear paint", importance="secondary")
    def paint_clear(ctx, targets, args):
        for t in targets:
            for s in list(ctx.item(t)["strokes"]):
                ctx.remove(s["id"])

    @registry.operation("paint.unlock", "Unlock paint layers so they take paint again.", target="paint",
                        label="Unlock", importance="secondary", valid_when={"is": ["locked", True]})
    def paint_unlock(ctx, targets, args):
        for t in every(ctx, targets):
            ctx.set(t, "locked", False)

    @registry.operation("stroke.add", "Paint one stroke into a paint layer: a path of points and a brush. Several "
                        "stroke.add calls in one call list are one undo step. On a seamless canvas the stroke wraps: paint "
                        "that crosses an edge comes back on the opposite side." + (
                            f" Instead of points, the app's own path ({', '.join(p.name for p in own)}: see each "
                            "field) may be given." if own else ""), target="paint", label="Paint",
                        params=[ID, *(_required(p) if p.name == "points" and not own else p for p in F.FIELDS["stroke"]),
                                *own])
    def stroke_add(ctx, targets, args):
        for t in targets:
            item = _new(ctx, "stroke", args if len(targets) == 1 else {**args, "id": None}, own)
            if "wrap" not in args and seamless(ctx, canvas_of(ctx.doc, ctx.kind.lists, t)):
                item["wrap"] = True
            _check_mask(ctx, t, item["mask"], item["id"])
            ctx.insert(t, "strokes", item)

    @registry.operation("fill.add", "Lay a fill (a closed area kept as its outline, fill.py) into a paint layer, in painting "
                        "order: to copy a fill; paint.fill makes one from a click.", target="paint", label="Add fill",
                        importance="secondary",
                        params=[ID, *(_required(p) if p.name == "points" else p for p in F.FIELDS["fill"])])
    def fill_add(ctx, targets, args):
        for t in targets:
            item = _new(ctx, "fill", args if len(targets) == 1 else {**args, "id": None})
            _check_mask(ctx, t, item["mask"], item["id"])
            ctx.insert(t, "strokes", item)

    @registry.operation("stroke.remove", "Delete strokes (and fills).", target=("stroke", "fill"), label="Delete stroke",
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


def _field_op(registry, type_, every=lambda ctx, targets: targets, extra=()):
    def set_fields(ctx, targets, args):
        for t in every(ctx, targets):
            for k, v in args.items():
                if k == "points" and type_ == "stroke":
                    v = with_pressure(v)
                if k == "mask":
                    _check_mask(ctx, t, v, t)
                ctx.set(t, k, v)
    label = F.LABELS[type_].lower()
    registry.operation(f"{type_}.set", f"Change a {label}'s settings.", target=type_, params=[*F.FIELDS[type_], *extra],
                       label=f"Edit {label}", fields=True)(set_fields)
