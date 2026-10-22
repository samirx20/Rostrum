"""Select first, then act: `style.apply` copies the look of one layer onto others. The screen's "copy style" is only a
clipboard holding the source layer's id; this is the one operation behind paste. The look is the table LOOK below (the
one colour is `fill` on shapes and paths and `color` on text); effects are copied, replacing the target's own. A field a
target doesn't have is left alone, and so is one that is animated or driven by an expression there; `skipped(...)` says
which, since an operation has no reply of its own."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.ids import counted
from rostrum_core.tree import bare, child_keys, index

from . import fields as F, grade_fields as G
from .exprbake import source_of
from .kind import REGISTRY as R

COLOUR = ("fill", "color")
LOOK = ("filled", "fillRule", "stroke", "strokeColor", "strokeWidth", "opacity", "blend", *(p.name for p in G.COLOUR))


def _has(item: dict, prop: str) -> bool:
    return F.param(item["type"], prop) is not None


def _value(item: dict, prop: str):
    return item.get(prop, F.param(item["type"], prop).default)


def _pairs(src: dict, dst: dict) -> list[tuple[str, str]]:
    """(source field, target field) for every look field both layers have; the colour is one field, whatever it is called."""
    sc, dc = (next((c for c in COLOUR if _has(i, c)), None) for i in (src, dst))
    return ([(sc, dc)] if sc and dc else []) + [(f, f) for f in LOOK if _has(src, f) and _has(dst, f)]


def _blocked(item: dict, prop: str) -> str:
    """Why `prop` can't take a plain value on `item` ("" when it can)."""
    if any(k["prop"] == prop for k in item.get("keys", [])):
        return "is animated there"
    return f"is driven by an expression ({source_of(item, prop)})" if source_of(item, prop) else ""


def skipped(data: dict, source: str, ids: list[str]) -> dict[str, list[str]]:
    """{target id: ["field: why", ...]}: what style.apply leaves alone on each target."""
    from .kind import KIND
    idx = index(data, KIND.lists)
    src, out = idx[source].item, {}
    for i in ids:
        dst = idx[i].item
        have = {d for _, d in _pairs(src, dst)}
        out[i] = [f"{d}: {why}" for _, d in _pairs(src, dst) if (why := _blocked(dst, d))]
        out[i] += [f"{f}: a {dst['type']} has none" for f in LOOK if _has(src, f) and f not in have]
    return out


@R.operation("style.apply", "Copy the look of one layer (`from`) onto the selected layers: colour (fill), outline, opacity, "
             "blend, colour adjustments, and its effects (copied, replacing theirs). A field a layer doesn't have, or that is "
             "animated or driven by an expression on it, is left alone; a layer that takes nothing from it is refused.",
             target=F.LAYERS, label="Paste style", importance="secondary",
             params=[Param.id("from", kind="layer", label="Copy the look of", required=True)])
def style_apply(ctx, targets, args):
    src, lists = ctx.item(args["from"]), ctx.kind.lists
    for t in targets:
        dst = ctx.item(t)
        if t == src["id"]:
            continue
        pairs = _pairs(src, dst)
        if not pairs and not (src.get("effects") or dst.get("effects")):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f"has nothing in common with {src['id']}'s look")
        for s, d in pairs:
            if not _blocked(dst, d) and _value(src, s) != _value(dst, d):
                ctx.set(t, d, _value(src, s))
        if src.get("effects") or dst.get("effects"):
            for e in list(dst.get("effects", [])):
                ctx.remove(e["id"])
            for e in src.get("effects", []):
                _copy(ctx, e, t, "effects", lists)


def _copy(ctx, item: dict, parent: str, key: str, lists: dict) -> None:
    """A copy of `item` (and what it holds) under `parent`, with new ids."""
    new = {**bare(item, lists), "id": counted(index(ctx.doc, lists), item["type"])}
    ctx.insert(parent, key, new)
    for k in child_keys(item, lists):
        for child in item.get(k, []):
            _copy(ctx, child, new["id"], k, lists)
