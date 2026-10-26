"""What an item is called. The id is the item's address and never changes; the name is what a person reads.

A new layer is named in words ("Text", then "Text 2", "Text 3" …). An older document may hold a layer whose name is only
its type's ("Text") with a meaningful id ("title"): there the id reads better, so it is shown instead. A text still
named "Text" or "Text 2" reads as its words, or "Counter" while it counts."""
from __future__ import annotations

import re

from . import fields as F


def display_name(item: dict) -> str:
    """The name to show: the item's name; its id while the name says nothing the id doesn't ("Text" on "title")."""
    name, id_ = item.get("name"), str(item["id"])
    if not name:
        return id_
    if name == F.LABELS.get(item.get("type")) and not re.fullmatch(rf"{re.escape(item['type'])}_\d+", id_):
        return id_
    if item.get("type") == "shape" and re.fullmatch(rf"{F.LABELS['shape']}( \d+)?", str(name)) and item.get("shape") in F.SHAPE_WORDS:
        return F.SHAPE_WORDS[item["shape"]] + str(name)[len(F.LABELS["shape"]):]      # a star not yet renamed is "Star", never "Shape"
    if item.get("type") == "text" and re.fullmatch(rf"{F.LABELS['text']}( \d+)?", str(name)):
        if item.get("counter"):
            return "Counter" + str(name)[len(F.LABELS["text"]):]      # a counting text shows a number, not its typed words
        if words(item):
            return words(item)              # a text the person hasn't named reads as its words, as in a design tool
    return str(name)


def words(item: dict, most: int = 32) -> str:
    """A text's first line, cut to `most` characters."""
    line = next((ln.strip() for ln in str(item.get("body", "")).splitlines() if ln.strip()), "")
    return line if len(line) <= most else line[:most - 1].rstrip() + "…"


def unique_name(taken: set[str], base: str) -> str:
    """`base`, or `base 2`, `base 3` … the first that no item has."""
    if base not in taken:
        return base
    n = 2
    while f"{base} {n}" in taken:
        n += 1
    return f"{base} {n}"


_DEFAULT_SHAPE = re.compile(rf"(Shape|{'|'.join(F.SHAPE_WORDS.values())})( \d+)?")


def after_set(ctx, target: str, args: dict):
    """Called by every field operation after it set `args`: a shape that still has its default name takes its kind's
    ("Ellipse", then "Ellipse 2"): the numbers count per kind from 1, not per layer. A name a person typed is kept."""
    item = ctx.item(target)
    if item["type"] != "shape" or args.get("shape") not in F.SHAPE_WORDS or not _DEFAULT_SHAPE.fullmatch(str(item.get("name", ""))):
        return
    from rostrum_core.tree import index
    others = [loc.item for i, loc in index(ctx.doc, ctx.kind.lists).items() if i != target and loc.item.get("type") != "doc"]
    taken = {display_name(i) for i in others} | {i["name"] for i in others if i.get("name")}
    ctx.set(target, "name", unique_name(taken, F.SHAPE_WORDS[args["shape"]]))
