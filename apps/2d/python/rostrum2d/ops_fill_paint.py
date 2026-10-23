"""`layer.fill`: a layer's whole fill in one call, one change (SPEC 2d-design-v2 § 6): its type, its colour or its
gradient's stops and geometry (fill_fields.py, fill_paint.py). The project's colours: `swatch.add / remove / rename`
(the picker's Project row; a swatch's colour changes with `swatch.set`).

A stop is written "<colour> <position %> [<opacity %>]": "#ff7a59 0", "#7c4dff 100", "#ffffff 40 50". Stops already on
the layer are changed in place, in order, so their keys stay (a re-run never wipes an animated stop); extra ones are
added, missing ones deleted. A colour or stop field that is animated gets a key at `at` (value.set), never a still
value its keys would hide; without `at` a change there is refused in words (a re-run writing the same value passes).
"""
from __future__ import annotations

import re

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import keys_of

from . import fill_fields as FF, fill_paint
from .evaluate import resolve
from .kind import REGISTRY as R

_STOP = re.compile(r"^\s*(#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?)\s+(-?\d+(?:\.\d+)?)\s*%?(?:\s+(\d+(?:\.\d+)?)\s*%?)?\s*$")
SWATCHES = "swatches"


def parse_stop(ctx, text: str) -> dict:
    m = _STOP.match(text or "")
    if not m:
        ctx.fail(codes.BAD_ARGUMENT, f'stop "{text}"', 'is not "<colour #rrggbb or #rrggbbaa> <position %> [<opacity %>]"', ["#ff7a59 0", "#7c4dff 100 80"])
    at, opacity = float(m[2]) / 100, (float(m[3]) / 100 if m[3] else 1.0)
    if not (0 <= at <= 1 and 0 <= opacity <= 1):
        ctx.fail(codes.BAD_ARGUMENT, f'stop "{text}"', "has a position or opacity outside 0 … 100 %")
    alpha = int(m[1][7:9], 16) / 255 if len(m[1]) == 9 else 1.0     # "#rrggbbaa": its alpha folds into the opacity
    return {"at": round(at, 4), "color": m[1][:7].lower(), "opacity": round(opacity * alpha, 4)}


@R.operation("layer.fill", "Set the fill of shapes, paths or texts in one change: none, a solid colour, or a linear / radial / "
             "angular gradient with its stops (\"#ff7a59 0\", \"#7c4dff 100\"; a third number is the stop's opacity %) and "
             "its angle (linear: 90 = left to right; angular: where the sweep starts, 0 = up) or centre (fractions of the box), or "
             "span=\"points\": linear from (x1, y1) to (x2, y2), radial radii rx, ry (fractions of the box); or a picture "
             "(file, fit fill / fit / tile / stretch, scale) clipped to a shape or path. "
             "Each stop's colour and position animate with key.add on the stop; an animated one changes at `at` (a key there).",
             target=FF.OWNERS, label="Fill",
             params=[Param.choice("type", ["none", *FF.TYPES], label="Fill type"),
                     Param.color("color", label="Colour", help="The solid colour (a text's letters)"),
                     Param.list("stops", "text", label="Stops", min_items=2, help="Each \"<colour> <position %> [<opacity %>]\""),
                     Param.number("angle", label="Angle", min=-360, max=360, unit="°"),
                     Param.number("cx", label="Centre X", min=-5, max=6), Param.number("cy", label="Centre Y", min=-5, max=6),
                     Param.choice("span", ["box", "points"], label="Span"),
                     *(Param.number(n, label=n, min=-5, max=6) for n in ("x1", "y1", "x2", "y2", "rx", "ry")),
                     Param.text("picture", label="Picture", help="A picture file (fill type picture)"),
                     Param.choice("fit", ["fill", "fit", "tile", "stretch"], label="Picture fit"),
                     Param.number("scale", label="Picture scale", min=0.01, max=100),
                     Param.number("at", label="At", help="The time an animated colour or stop changes at (a key there)")])
def fill_set(ctx, targets, args):
    stops = [parse_stop(ctx, s) for s in args["stops"]] if args.get("stops") else None
    for t in targets:
        item = ctx.item(t)
        kind = args.get("type") or fill_paint.kind_of(item)
        if kind == "none":
            if item["type"] == "text":
                ctx.fail(codes.BAD_ARGUMENT, f'text "{t}"', "can't have no fill (its letters would vanish); hide it or set its opacity")
            ctx.set(t, "filled", False)
            continue
        if item["type"] != "text" and not item.get("filled", True):
            ctx.set(t, "filled", True)
        ctx.set(t, "fillType", kind)
        if "color" in args:
            _put(ctx, item, fill_paint.colour_field(item), args["color"], args.get("at"))
        if kind == "picture" and item["type"] == "text":
            ctx.fail(codes.BAD_ARGUMENT, f'text "{t}"', "takes no picture fill yet; use a colour or a gradient")
        for field, name in (("gradAngle", "angle"), ("gradX", "cx"), ("gradY", "cy"), ("fillPicture", "picture"),
                            ("fillFit", "fit"), ("fillScale", "scale"), *((f, s) for f, s in fill_paint.GEOMETRY.items())):
            if name in args:
                ctx.set(t, field, args[name])
        if kind in FF.GRADIENTS:
            _set_stops(ctx, t, stops or (None if item.get("stops") else _first_stops(item)), args.get("at"))


def _first_stops(item: dict) -> list[dict]:
    """A solid fill becoming a gradient: its colour to black."""
    return [{"at": 0.0, "color": item.get(fill_paint.colour_field(item), "#ffffff"), "opacity": 1.0},
            {"at": 1.0, "color": "#000000", "opacity": 1.0}]


def _put(ctx, owner: dict, prop: str, value, at):
    """A still field changes; an animated one gets a key at `at` (the generic value.set) when it isn't that already."""
    if not keys_of(owner, prop):
        if owner.get(prop) != value:
            ctx.set(owner["id"], prop, value)
    elif at is None:
        if owner.get(prop) == value:                     # a re-run writing what it wrote before: the keys stay
            return
        ctx.fail(codes.BAD_ARGUMENT, '"at"', f'is needed: {owner["id"]}.{prop} is animated', hint="Give the time.")
    elif resolve(owner, at)[prop] != value:
        R.get("value.set").fn(ctx, [owner["id"]], {"prop": prop, "at": at, ("c" if prop == "color" or prop == "fill" else "v"): value})


def _set_stops(ctx, t: str, stops: list[dict] | None, at=None):
    if stops is None:
        return
    have = fill_paint.stops_of(ctx.item(t))
    for old, new in zip(have, stops):
        for k, v in new.items():
            _put(ctx, old, k, v, at)
    for new in stops[len(have):]:
        ctx.insert(t, "stops", {"id": ctx.new_id("stop"), "type": "stop", "name": "Gradient stop", **new, "keys": []})
    for old in have[len(stops):]:
        ctx.remove(old["id"])


# ── the project's colours ─────────────────────────────────────────────────────────────────────────────────────────

def swatches(doc: dict) -> list[dict]:
    return doc.get(SWATCHES, [])


@R.operation("swatch.add", "Save a colour to the project's colours (the colour picker's Project row).", label="Save colour",
             params=[Param.color("color", label="Colour", required=True), Param.text("name", label="Name")])
def swatch_add(ctx, targets, args):
    if any(s["color"] == args["color"] for s in swatches(ctx.doc)):
        ctx.fail(codes.BAD_ARGUMENT, f'colour {args["color"]}', "is already one of the project's colours")
    ctx.insert("root", SWATCHES, {"id": ctx.new_id("swatch"), "type": "swatch", "name": args.get("name") or args["color"].upper(),
                                  "color": args["color"]})


@R.operation("swatch.remove", "Take colours off the project's colours (layers keep theirs).", target="swatch", label="Remove colour")
def swatch_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)


@R.operation("swatch.rename", "Rename one of the project's colours.", target="swatch", label="Rename colour",
             params=[Param.text("name", label="Name", required=True)])
def swatch_rename(ctx, targets, args):
    for t in targets:
        ctx.set(t, "name", args["name"])
