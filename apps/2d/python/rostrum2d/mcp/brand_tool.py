"""The project's brand kit for agents (rostrum2d/brand_kit.py, the screen's Library › Brand kit uses the same):

    run_brand_kit {what: list}                                                    its colours, text styles and logos
    run_brand_kit {what: change, do: add|remove, section, name, value?, file?, style?}   change the kit (`style`: copy a document's text style)
    run_brand_kit {what: use, section, name, layers, item?}                       a kit colour or text style on layers, as one undo step

A logo is placed with run_import {path: <its file>, fit: true}. A document's own text styles are operations
(style.define, style.use, textstyle.set …); the kit is the project's, shared by every document.
"""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import brand_kit as B
from .. import text_styles

tools = Tools()
SECTION = {"type": "string", "enum": list(B.SECTIONS), "description": "colors, textStyles or logos."}


def _folder(ctx, doc=None) -> str:
    folder = (doc.folder if doc is not None else None) or ctx.app.folder
    if not folder:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "the brand kit", "needs a project folder: none is open")
    return str(folder)


def _say(kit: dict) -> str:
    return "; ".join(f'{s}: {", ".join(e["name"] for e in kit[s]) or "none"}' for s in B.SECTIONS)


@tools.tool("inspect_brand_kit", {"properties": {}})
def inspect_brand_kit(ctx, args):
    """The project's brand kit, shared by every document of the project: colours {name, value}, text styles {name,
    font, size, weight, color, …} and logos {name, file relative to the project}. Use one with run_brand_kit (what: use); place a
    logo with run_import {path: file, fit: true}."""
    kit = B.read(_folder(ctx))
    return Reply(f"Brand kit: {_say(kit)}.", {"kit": kit})


@tools.tool("run_brand_kit", {"properties": {
    "do": {"type": "string", "enum": ["add", "remove"]}, "section": SECTION,
    "name": {"type": "string", "description": "The entry's name; adding a name that is there replaces it (an update)."},
    "value": {"type": "string", "description": "colors: the colour, #rrggbb."},
    "file": {"type": "string", "description": "logos: the picture (svg, png, pdf, psd …), relative to the project or absolute; kept in the project (media/brand/, named by its content)."},
    "style": {"type": "string", "description": "textStyles: the id of a document text style to copy into the kit (its values)."},
    "item": {"type": "string", "description": "With `style`: the document holding it. Optional when one is open."}},
    "required": ["do", "section", "name"]})
def run_brand_kit(ctx, args):
    """Add an entry to the project's brand kit (or replace the one of that name), or remove one. A text style comes
    from a document's style (`style`), so it is made once on a text with style.define and then shared."""
    folder, section = _folder(ctx), args["section"]
    if args["do"] == "remove":
        return Reply(f'Removed "{args["name"]}". {_say(B.remove(folder, section, args["name"]))}.', {})
    entry = {"name": args["name"]}
    if section == "colors":
        entry["value"] = args.get("value")
    elif section == "logos":
        entry["file"] = args.get("file", "")
    else:
        doc = ctx.document(args.get("item"))
        if not args.get("style") or not doc.has(args["style"]):
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "style", "must be the id of a text style in the document",
                               [s["id"] for s in text_styles.styles(doc.data)])
        entry.update(text_styles.values(doc.item(args["style"])))
    kit = B.add(folder, section, entry)
    return Reply(f'Brand kit now: {_say(kit)}.', {"kit": kit})


@tools.tool("run_brand_use", {"properties": {
    "section": {"type": "string", "enum": ["colors", "textStyles"]}, "name": {"type": "string"},
    "layers": {"type": "array", "items": {"type": "string"}, "description": "Layer ids: a colour goes on shapes, paths and texts; a text style on texts."},
    "item": {"type": "string", "description": "The document. Optional when one is open."}},
    "required": ["section", "name", "layers"]})
def run_brand_use(ctx, args):
    """Put a brand kit colour or text style on layers, as one undo step. A text style becomes the document's style
    of that name (made, or refreshed to the kit's values) and the texts follow it, so changing it later changes them."""
    doc = ctx.document(args.get("item"))
    row = B.entry(_folder(ctx, doc), args["section"], args["name"])
    calls = B.use_calls(doc, args["section"], row, list(args["layers"]))
    ctx.apply(doc, calls, label=f'Use {args["name"]}')
    return Reply(f'"{args["name"]}" on {", ".join(args["layers"])} ({len(calls)} operations).', {"calls": len(calls)})
