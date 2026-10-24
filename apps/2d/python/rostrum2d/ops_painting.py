"""Paintings (paintings.py): `painting.add` (blank, or from an element's own paint, which moves, or a drawing, which is
copied; `onto` lays it as the fill of layers), `painting.set` (the generated field operation: name, size, Seamless, Draw
each frame, Loop), `painting.duplicate`, `painting.remove` (its uses become a solid fill of its average colour). The
strokes are the painting kit's, on the painting's frames (`stroke.add`, `paint.stroke` with canvas px …). Each is one
change, so one undo step takes back everything it did.
"""
from __future__ import annotations

import copy

from rostrum_core import Param
from rostrum_core.errors import codes

from . import drawing as D, fields as F, fill_paint, paintings, shared_paints
from .evaluate import resolve
from .kind import REGISTRY as R
from .names import display_name, unique_name
from .ops_draw import _copy_ids
from .ops_items import ID, NAME
from .sizes import own_size

BIGGEST_START = 2048        # a painting made for a layer starts at its box, the long side at most this
FILLABLE = ("shape", "path")


def _names(ctx) -> set[str]:
    return {p.get("name") for p in paintings.all_of(ctx.doc)}


def _start_size(ctx, layer_id: str) -> tuple[int, int]:
    """The size of a layer's box now, long side capped (ratio kept): what a painting made for it starts as."""
    item = ctx.item(layer_id)
    w, h = own_size(item["type"], resolve(item, 0.0))
    k = min(1.0, BIGGEST_START / max(w, h, 1.0))
    return max(1, round(w * k)), max(1, round(h * k))


def _fillable(ctx, t: str):
    item = ctx.item(t)
    if item["type"] not in FILLABLE:
        ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', f"is a {item['type']}: only shapes and paths take a painted fill", hint="Texts follow later.")
    if item.get("locked"):
        ctx.fail(codes.CONFLICT, f'"{t}"', "is locked", hint="Unlock it first.")
    return item


def _use(ctx, t: str, painting_id: str, fit: str):
    ctx.set(t, "filled", True)
    ctx.set(t, "fillType", "painted")
    ctx.set(t, "fillPainting", painting_id)
    ctx.set(t, "fillFit", fit)


def _copy_drawings(ctx, source: dict, painting_id: str):
    """The source's drawings copied into the painting, one at a time (each insert gives the next its own ids)."""
    for f in source.get("frames", []):
        frame = copy.deepcopy(f)
        frame["id"] = ctx.new_id("frame")
        _copy_ids(ctx, frame)
        ctx.insert(painting_id, "frames", frame)


def _copy_drawings(ctx, source: dict, painting_id: str):
    """The source's drawings copied into the painting, one at a time (each insert gives the next its own ids)."""
    for f in source.get("frames", []):
        frame = copy.deepcopy(f)
        frame["id"] = ctx.new_id("frame")
        _copy_ids(ctx, frame)
        ctx.insert(painting_id, "frames", frame)


@R.operation("painting.add", "Make a painting of this scene: a canvas (w × h px, up to 8192) that shapes and paths can use as "
             "their fill, edited once for every layer using it. Blank (one paint layer, Ink); or `from` a layer's own paint "
             "(Make painted fill: its paint MOVES into the painting and the layer's fill becomes it, looking the same; the "
             "layer's solid fill, if it has one, becomes its Colour under it) or from a drawing layer (its drawings are COPIED; "
             "the drawing stays). `onto` lays it as the fill of those layers (fit: stretch, fill, fit or tile).",
             label="New painting",
             params=[ID, NAME,
                     Param.number("w", label="Width", min=1, max=8192, integer=True, unit="px",
                                  help="Default: the first `onto` layer's width (long side at most 2048), else 512"),
                     Param.number("h", label="Height", min=1, max=8192, integer=True, unit="px"),
                     Param.toggle("seamless", label="Seamless", default=False, importance="secondary"),
                     Param.id("from", label="From", importance="secondary",
                              help="A shape / path with paint of its own (its paint moves in), or a drawing layer (copied); size comes from it"),
                     Param.list("onto", "id", label="Use on", importance="secondary", help="Layers (shapes, paths) whose fill becomes it"),
                     Param.choice("fit", ["fill", "fit", "tile", "stretch"], label="Fit", default="stretch", importance="secondary",
                                  help="How it covers the `onto` layers: stretch = the box (strokes land 1:1 from a box-sized painting)")])
def painting_add(ctx, targets, args):
    src = ctx.item(args["from"]) if args.get("from") else None
    onto = list(args.get("onto") or [])
    if src is not None:
        w, h = _source_size(ctx, src, args)
        if src["type"] != "drawing":
            onto = [src["id"], *(t for t in onto if t != src["id"])]
    else:
        w, h = args.get("w"), args.get("h")
        if (w is None or h is None) and onto:
            sw, sh = _start_size(ctx, onto[0])
            w, h = w or sw, h or sh
        w, h = w or 512, h or 512
    for t in onto:
        _fillable(ctx, t)
    pid = args.get("id") or ctx.new_id("painting")
    if pid in ctx.idx:
        ctx.fail(codes.BAD_ARGUMENT, f'id "{pid}"', "is already used in this document")
    if args.get("name"):
        base = args["name"]
    elif src is not None:
        base = display_name(src) if src["type"] == "drawing" else f"{display_name(src)} paint"
    else:
        base = f"{display_name(ctx.item(onto[0]))} paint" if onto else "Painting"
    painting = {"id": pid, "type": "painting", **F.defaults("painting"), "name": unique_name(_names(ctx), base), "w": w, "h": h,
                "seamless": bool(args.get("seamless")), "frames": []}
    if src is not None:
        painting.update({k: src[k] for k in ("eachFrame", "newHold") if k in src})
        if src.get("loop") in ("loop", "pingpong"):
            painting["loop"] = src["loop"]
    ctx.insert("root", "paintings", painting)
    if src is None:
        ctx.insert(pid, "frames", shared_paints.blank_frame(ctx, {}, 0))
    elif src["type"] == "drawing":
        _copy_drawings(ctx, src, pid)
    else:                                # its own paint moves in; its solid fill stays visible as the colour under it
        under = src.get("fill") if src.get("filled", True) and fill_paint.kind_of(src) == "solid" else None
        for f in list(src.get("frames", [])):
            ctx.move(f["id"], pid, "frames")
        for field, value in (("paintW", 0), ("paintH", 0), ("eachFrame", False)):
            ctx.set(src["id"], field, value)
        if under:
            ctx.set(src["id"], "fillUnder", under)
    for t in onto:
        _use(ctx, t, pid, "stretch" if src is not None and t == src["id"] else args.get("fit", "stretch"))


def _source_size(ctx, src: dict, args: dict) -> tuple[int, int]:
    """The painting's size from what it is made from, refusing (in words) what a painted fill can't be made from."""
    if {"w", "h"} & set(args):
        ctx.fail(codes.BAD_ARGUMENT, "w / h", "come from `from`, not from the call", hint="Leave them out, then painting.set the size.")
    if src["type"] == "drawing":
        return D.canvas_size(src)
    if src["type"] not in FILLABLE:
        ctx.fail(codes.BAD_ARGUMENT, f'from "{src["id"]}"', f"is a {src['type']}: Make painted fill takes a shape or path with its own "
                 "paint, or a drawing layer")
    if not src.get("frames") or not src.get("paintW"):
        ctx.fail(codes.BAD_ARGUMENT, f'from "{src["id"]}"', "has no paint of its own to make a painted fill from")
    if not src.get("paintInside", True):
        ctx.fail(codes.BAD_ARGUMENT, f'from "{src["id"]}"', "has paint that shows outside its outline; a fill is always inside it",
                 hint="Turn on Inside the outline (paintInside) first.")
    if fill_paint.kind_of(src) not in ("none", "solid"):
        ctx.fail(codes.BAD_ARGUMENT, f'from "{src["id"]}"', f'has a {fill_paint.kind_of(src)} fill under its paint, which a painted '
                 "fill would replace", hint="Make its fill solid or none first.")
    return D.canvas_size(src)


@R.operation("painting.duplicate", "Copy paintings (their drawings and strokes) under new names, \"<name> copy\", unused: to make one "
             "layer's texture differ, duplicate and use the copy on it.", target="painting", label="Duplicate painting",
             importance="secondary")
def painting_duplicate(ctx, targets, args):
    for t in targets:
        src = ctx.item(t)
        new = {**{k: v for k, v in src.items() if k != "frames"}, "id": ctx.new_id("painting"), "frames": []}
        new["name"] = unique_name(_names(ctx), f'{src.get("name", "Painting")} copy')
        ctx.insert("root", "paintings", new, ctx.idx[t].index + 1)
        _copy_drawings(ctx, src, new["id"])


@R.operation("painting.remove", "Delete paintings. Layers using one get a solid fill of its average colour instead (never left "
             "pointing at nothing); one undo brings the painting and every use back.", target="painting",
             label="Delete painting", importance="secondary")
def painting_remove(ctx, targets, args):
    for t in targets:
        colour, cover = paintings.average(ctx.item(t))
        for layer in paintings.uses(ctx.doc, t, ctx.kind.lists):
            under = layer.get("fillUnder")        # over a colour, the colour shows where the painting does not
            shown = _mix(colour, under, cover) if under else colour
            opacity = layer.get("fillOpacity", 1.0) * (1.0 if under else cover)
            for field, value in (("fillType", "solid"), ("fill", shown), ("fillOpacity", round(opacity, 4)),
                                 ("fillPainting", ""), ("fillUnder", None)):
                ctx.set(layer["id"], field, value)
        ctx.remove(t)


def _mix(top: str, bottom: str, cover: float) -> str:
    a, b = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (top, bottom))
    return "#%02x%02x%02x" % tuple(round(x * cover + y * (1 - cover)) for x, y in zip(a, b))
