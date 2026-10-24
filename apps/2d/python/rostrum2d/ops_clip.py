"""Copy and paste of layers. `copied(doc, ids)` is what Copy puts on the clipboard: the chosen layers (the top-most
ones: a layer inside another chosen one comes with it), bottom of the stack first, each whole (keys, effects, masks,
layers inside). `layer.paste` lands such a list in a group or composition, in place: same names and settings, new ids
throughout, links between the pasted layers following their new ids (a matte, a path to follow, a rig's binds).
A link to a layer that didn't come along is dropped (`LAYER_LINKS`): it would point at a stranger, or nothing.
"""
from __future__ import annotations

import json

from rostrum_core import Param, ids
from rostrum_core.errors import codes
from rostrum_core.tree import bare, child_keys, index, walk

from . import fields as F
from .kind import REGISTRY as R
from .ops_items import LAYER_HOLDERS

LAYER_LINKS = ("matte", "pathLayer", "ridePath")      # fields naming another layer by id (fields.py); kept only within the paste


def copied(data: dict, lists: dict, ids_: list[str]) -> list[dict]:
    """The chosen layers' data for the clipboard, bottom of the stack first; one inside another chosen one comes
    with its holder, not twice."""
    idx = index(data, lists)
    inside = {d["id"] for i in ids_ for d in walk(idx[i].item, lists) if d["id"] != i}
    top = [i for i in ids_ if i not in inside]
    return [json.loads(json.dumps(idx[i].item)) for i in sorted(top, key=lambda i: (idx[i].parent, idx[i].index))]


@R.operation("layer.paste", "Paste layers as Copy put them: the layers' data (JSON, bottom of the stack first), into a "
             "group or composition (the first composition when left out), on top unless index is given. Names and "
             "settings stay; every id is new; links to layers that didn't come along are dropped.",
             label="Paste", importance="secondary",
             params=[Param.text("layers", label="Layers", required=True, help="The copied layers, as JSON"),
                     Param.id("into", label="Into", help="A group or composition"),
                     Param.number("index", label="Position", min=0, max=100000, integer=True, importance="deep",
                                  help="0 = bottom of the stack; on top when left out")])
def layer_paste(ctx, targets, args):
    lists = ctx.kind.lists
    try:
        layers = json.loads(args["layers"])
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, '"layers"', f"is not JSON ({e})")
    if not isinstance(layers, list) or not layers or not all(isinstance(x, dict) and x.get("type") in F.PLACED for x in layers):
        ctx.fail(codes.BAD_ARGUMENT, '"layers"', "must be a list of layers, as Copy gives them", list(F.PLACED))
    comps = ctx.doc.get("comps", [])
    into = args.get("into") or (comps[0]["id"] if comps else "")
    holder = ctx.item(into)
    if holder["type"] not in LAYER_HOLDERS:
        ctx.fail(codes.BAD_ARGUMENT, f'into "{into}"', f"is a {holder['type']}, not a group or composition")
    taken = set(index(ctx.doc, lists))
    new = {}
    for d in (d for layer in layers for d in walk(layer, lists)):
        if not isinstance(d.get("id"), str) or not d.get("type"):
            ctx.fail(codes.BAD_ARGUMENT, '"layers"', f"has an item without an id or type: {str(d)[:60]}")
        new[d["id"]] = ids.counted(taken, d["type"])
        taken.add(new[d["id"]])
    at = args.get("index")
    for n, layer in enumerate(layers):
        _put(ctx, lists, layer, into, "layers", None if at is None else at + n, new)


def _put(ctx, lists, item, parent, key, at, new):
    words = _words(item["type"])
    out = {k: v if k in words else _relink(v, new) for k, v in bare(item, lists).items()}
    out["id"] = new[item["id"]]
    for k in LAYER_LINKS:
        if out.get(k) and out[k] not in new.values():
            out[k] = ""
    ctx.insert(parent, key, out, at)
    for k in child_keys(item, lists):
        for child in item.get(k, []):
            _put(ctx, lists, child, out["id"], k, None, new)


def _words(type_) -> set[str]:
    """The item's fields that are settings, never links (a text's words may happen to equal an id): every field of
    its field operation except id fields and LAYER_LINKS. Anything else (a bind's layer and bone) may be a link."""
    op = R.field_op(type_)
    return {p.name for p in op.params if p.type != "id" and p.name not in LAYER_LINKS} if op else set()


def _relink(v, new):
    """A value naming a pasted item by its old id names its copy instead (in lists too)."""
    if isinstance(v, str):
        return new.get(v, v)
    if isinstance(v, list):
        return [_relink(x, new) for x in v]
    return v
