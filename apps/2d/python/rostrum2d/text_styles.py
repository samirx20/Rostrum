"""Named text styles (UX_SPEC 3.27, "Colour and text styles"): the document's `textStyles` list, each a `textstyle`
item with a name and the type fields of a text (fields.STYLED: font, size, weight, colour, letter spacing, line height …).
A text follows one through its `textStyle` field.

One source of truth, and every reader sees plain fields: the style's values are written onto each text that follows it
in the same change that sets them (`after_set`, which every field operation calls), so the inspector, the engine, export
and agents all read a text's own fields. Setting a styled field on a following text by hand cuts the link (the text
keeps its value, as Figma's detach), so a later change to the style never undoes what a person set.

    style.define  {name?}      on one text: a new style from its type, and the text follows it
    style.use     {style}      on texts: they follow the style (its values are written onto them)
    style.detach               on texts: they keep their values and follow nothing
    style.remove               on styles: gone; the texts that followed them keep their values
    textstyle.set {size, …}    change a style: every text following it changes in the same step (kind.py's field op)
    text.set {textStyle: id}   the same as style.use ("" = style.detach)
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import fields as F
from .kind import REGISTRY as R
from .names import unique_name

LIST = "textStyles"            # on the document root


def styles(data: dict) -> list[dict]:
    return data.get(LIST, [])


def values(item: dict) -> dict:
    """The styled fields of a text or a style, defaults filled in."""
    return {f: item.get(f, F.param(item["type"], f).default) for f in F.STYLED}


def _followers(ctx, style_id: str) -> list[dict]:
    return [loc.item for loc in ctx.idx.values() if loc.item.get("type") == "text" and loc.item.get("textStyle") == style_id]


def _write(ctx, text: dict, vals: dict):
    for k, v in vals.items():
        if text.get(k, F.param("text", k).default) != v:
            ctx.set(text["id"], k, v)


def _style(ctx, style_id: str, where: str) -> dict:
    if style_id not in ctx.idx or ctx.idx[style_id].item.get("type") != "textstyle":
        ctx.fail(codes.NOT_FOUND, where, f'text style "{style_id}"', "is not a text style in this document",
                 [s["id"] for s in styles(ctx.doc)])
    return ctx.item(style_id)


def after_set(ctx, target: str, args: dict):
    """Called by every field operation after it set `args` on `target`: a style's change reaches its texts; a text
    told to follow a style takes its values; a styled field set by hand on a following text detaches it."""
    item = ctx.item(target)
    if item["type"] == "textstyle":
        changed = {k: v for k, v in args.items() if k in F.STYLED}
        for text in _followers(ctx, target) if changed else []:
            _write(ctx, text, changed)
    elif item["type"] == "text" and args.get("textStyle"):
        _write(ctx, item, values(_style(ctx, args["textStyle"], f'text "{target}"')))
    elif item["type"] == "text" and item.get("textStyle") and "textStyle" not in args:
        style = values(_style(ctx, item["textStyle"], f'text "{target}"'))
        if any(k in style and v != style[k] for k, v in args.items()):
            ctx.set(target, "textStyle", "")


@R.operation("style.define", "Save the type of a text (font, size, weight, colour, letter spacing, line height …) as a "
             "named text style; the text then follows it. Changing the style later (textstyle.set) changes every text "
             "that follows it.", target="text", label="Save as style",
             params=[Param.text("name", label="Name", help="The style's name; the text's name when left out"),
                     Param.text("id", label="Id", importance="deep", help="Optional; counted (textstyle_1 …) when left out")])
def style_define(ctx, targets, args):
    text = ctx.item(targets[0])
    taken = {s["name"] for s in styles(ctx.doc)}
    name = args.get("name") or unique_name(taken, text.get("name") or "Text style")
    if name in taken:
        ctx.fail(codes.BAD_ARGUMENT, f'name "{name}"', "is already a text style's name", sorted(taken))
    id_ = args.get("id") or ctx.new_id("textstyle")
    if id_ in ctx.idx:
        ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
    ctx.insert("root", LIST, {"id": id_, "type": "textstyle", "name": name, **values(text)})
    for t in targets:
        ctx.set(t, "textStyle", id_)
        _write(ctx, ctx.item(t), values(ctx.item(id_)))


@R.operation("style.use", "Make texts follow a named text style: they take its font, size, weight, colour … now and "
             "whenever the style changes.", target="text", label="Use style",
             params=[Param.id("style", kind="textstyle", label="Style", required=True)])
def style_use(ctx, targets, args):
    vals = values(_style(ctx, args["style"], "style.use"))
    for t in targets:
        ctx.set(t, "textStyle", args["style"])
        _write(ctx, ctx.item(t), vals)


@R.operation("style.detach", "Texts stop following their text style; they keep how they look.", target="text",
             label="Detach style", importance="secondary")
def style_detach(ctx, targets, args):
    for t in targets:
        if not ctx.item(t).get("textStyle"):
            ctx.fail(codes.BAD_ARGUMENT, f'text "{t}"', "follows no text style")
        ctx.set(t, "textStyle", "")


@R.operation("style.remove", "Delete text styles; the texts that followed them keep how they look.", target="textstyle",
             label="Delete style", importance="secondary")
def style_remove(ctx, targets, args):
    for s in targets:
        for text in _followers(ctx, s):
            ctx.set(text["id"], "textStyle", "")
        ctx.remove(s)
