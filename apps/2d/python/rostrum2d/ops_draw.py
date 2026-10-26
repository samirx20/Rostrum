"""Frame-by-frame operations on drawing layers: add a drawing at a frame (blank, or copying another to redraw on),
remove one, hold one for N frames, move one to another frame. Painting itself is the shared kit's (`stroke.add`, `paint.clear` …: kind.py
registers it). A drawing's frames stay sorted by `at` (the kind's check refuses anything else).
"""
from __future__ import annotations

import copy

from rostrum_core import Param
from rostrum_core.keys import keys_of
from rostrum_core.errors import codes
from rostrum_core.tree import index
from rostrum_paint import linked

from . import paint_fields, shared_paints
from .kind import REGISTRY as R


def starter_frame(ctx, at: int = 0, id_: str | None = None) -> dict:
    """A new layer's first drawing: one frame holding one paint layer ("Ink")."""
    return shared_paints.blank_frame(ctx, {}, at, id_)


def _fresh(ctx, type_, *pending) -> str:
    """A counted id not used in the document nor by items about to be inserted."""
    taken = set(index(ctx.doc, ctx.kind.lists))
    for item in pending:
        taken |= {item["id"], *(p["id"] for p in item.get("paints", []))}
    n = 1
    while f"{type_}_{n}" in taken:
        n += 1
    return f"{type_}_{n}"


def _place(frames, at) -> int:
    return sum(1 for f in frames if f["at"] < at)


@R.operation("frame.add", "Add a drawing at a frame to a drawing layer, a painted element or a painting (blank, or a copy "
             "of another drawing to redraw on; a painting's drawings boil in every layer using it, each use from its own "
             "start, and always loop). It shows until the next drawing; Draw each frame turns on in the same change. "
             "Frame left out: after the last drawing, its hold being the layer's New ones hold (newHold, default 2). "
             "Every drawing of a layer has the same paint layers: a blank one starts with them empty, a copy with the "
             "copied strokes in them.",
             target=("drawing", "painting", *paint_fields.TYPES), label="New drawing",
             params=[Param.number("at", label="Frame", min=0, max=10**7, integer=True),
                     Param.id("copy", kind="frame", label="Copy of", importance="secondary",
                              help="A frame id whose paint layers are copied"),
                     Param.text("id", label="Id", importance="deep")])
def frame_add(ctx, targets, args):
    for t in targets:
        frames = ctx.item(t).get("frames", [])
        args = {**args, "at": args["at"] if args.get("at") is not None else next_at(ctx.item(t))}
        if any(f["at"] == args["at"] for f in frames):
            ctx.fail(codes.BAD_ARGUMENT, f'at={args["at"]}', f"{t} already has a drawing at that frame")
        if args.get("copy"):
            src = ctx.item(args["copy"])
            if src["type"] != "frame":
                ctx.fail(codes.BAD_ARGUMENT, f'copy "{args["copy"]}"', f"is a {src['type']}, not a drawing frame")
            if frames and index(ctx.doc, ctx.kind.lists)[src["id"]].parent != t:
                ctx.fail(codes.BAD_ARGUMENT, f'copy "{args["copy"]}"', f"is a drawing of another layer: {t}'s drawings "
                         "share their own paint layers", hint="Copy one of its own drawings.")
            frame = copy.deepcopy(src)
            frame.update(id=args.get("id") or ctx.new_id("frame"), at=args["at"])
            _copy_ids(ctx, frame)
        else:
            frame = shared_paints.blank_frame(ctx, ctx.item(t), args["at"], args.get("id"))
        ctx.insert(t, "frames", frame, _place(frames, args["at"]))
        if not ctx.item(t).get("eachFrame"):
            ctx.set(t, "eachFrame", True)


def next_at(item: dict) -> int:
    """Where a new drawing goes when no frame is given: the last one's start + the layer's New ones hold."""
    frames = item.get("frames", [])
    return frames[-1]["at"] + int(item.get("newHold") or 2) if frames else 0


def _copy_ids(ctx, frame):
    taken = set(index(ctx.doc, ctx.kind.lists)) | {frame["id"]}

    def fresh(type_):
        n = 1
        while f"{type_}_{n}" in taken:
            n += 1
        taken.add(f"{type_}_{n}")
        return f"{type_}_{n}"
    for p in frame["paints"]:
        p["layer"] = linked.key(p)          # the copy stays in the same shared paint layer
        p["id"] = fresh("paint")
        for s in p["strokes"]:
            s["id"] = fresh("stroke")
    old = {m["id"]: fresh("paintmask") for m in frame["paintmasks"]}
    for m in frame["paintmasks"]:
        m["id"] = old[m["id"]]
    for p in frame["paints"]:
        for s in p["strokes"]:
            s["mask"] = old.get(s["mask"], s["mask"])


@R.operation("frame.remove", "Delete drawings from a drawing layer (the one before is then held longer).",
             target="frame", label="Delete drawing", importance="secondary")
def frame_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)


@R.operation("frame.hold", "Show a drawing for this many frames: every later drawing of the layer moves by the "
             "difference.", target="frame", label="Hold",
             params=[Param.number("frames", label="Frames", min=1, max=10**6, integer=True, required=True)])
def frame_hold(ctx, targets, args):
    for t in targets:
        drawing = ctx.item(index(ctx.doc, ctx.kind.lists)[t].parent)
        frames = drawing["frames"]
        i = next(n for n, f in enumerate(frames) if f["id"] == t)
        if i + 1 == len(frames):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', "is the last drawing: it is held to the end already",
                     hint="Add a drawing after it (frame.add) to end the hold.")
        shift = frames[i]["at"] + args["frames"] - frames[i + 1]["at"]
        for f in frames[i + 1:]:
            ctx.set(f["id"], "at", f["at"] + shift)


@R.operation("frame.move", "Move a drawing to another frame; the others stay where they are (the one before it is held "
             "until it, or until the next). Refused where another drawing already starts.",
             target="frame", label="Move drawing", importance="secondary",
             params=[Param.number("to", label="Frame", min=0, max=10**7, integer=True, required=True)])
def frame_move(ctx, targets, args):
    if len(targets) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "target", "move one drawing at a time", hint="Call frame.move once per drawing.")
    t, to = targets[0], args["to"]
    parent = index(ctx.doc, ctx.kind.lists)[t].parent
    frames = ctx.item(parent)["frames"]
    if any(f["at"] == to and f["id"] != t for f in frames):
        ctx.fail(codes.BAD_ARGUMENT, f"to={to}", f"{parent} already has a drawing at that frame")
    others = [f for f in frames if f["id"] != t]
    ctx.set(t, "at", to)
    ctx.move(t, parent, "frames", _place(others, to))


@R.operation("drawing.centre", "Turn a new drawing about its middle, as every drawn shape does, without moving anything you see "
             "(the pen's first stroke starts a drawing where the stroke began, so its turning point sat there). Only a drawing "
             "not turned, stretched or keyed at its position, scale and turning point.", target="drawing",
             label="Centre the turning point", importance="deep")
def drawing_centre(ctx, targets, args):
    for t in targets:
        item = ctx.item(t)
        if item.get("rotation") or any(keys_of(item, p) for p in ("x", "y", "scale", "scaleX", "scaleY", "rotation", "anchorX", "anchorY")):
            continue
        w, h = int(item.get("w", 1920)), int(item.get("h", 1080))
        k = item.get("scale", 1.0)
        for axis, size, stretch in (("X", w, item.get("scaleX", 1.0)), ("Y", h, item.get("scaleY", 1.0))):
            move = (0.5 - item.get("anchor" + axis, 0.5)) * size * k * stretch
            if abs(move) > 1e-6:
                ctx.set(t, axis.lower(), item.get(axis.lower(), 0.0) + move)
                ctx.set(t, "anchor" + axis, 0.5)
