"""Move and copy the selected notes, drum hits and clips: `<kind>.move` (nudge, paste at an offset) and
`<kind>.duplicate` (copies placed `by` an amount, default right after the selection's end). One maker per kind.
A layered clip's group moves with it (like `clip.set at`). New ids of a copy: `select_time.inserted(change)`.
"""
from __future__ import annotations

import copy

from rostrum_core import codes

from . import ids
from .ops_group import mates
from .registry import REGISTRY, taken
from .select_time import BY, BY_REQUIRED, KINDS, end_of, moved, start_of

LABELS = {"note": "note", "hit": "drum hit", "clip": "clip"}


def _with_group(ctx, targets, kind):
    """The targets, plus (for clips) the layered group mates they carry."""
    out = list(targets)
    if kind == "clip":
        for t in targets:
            out += [c["id"] for c in mates(ctx, t) if c["id"] not in out]
    return out


def _new_id(kind, track, item, ctx):
    have, root = taken(ctx), ctx.doc
    if kind == "note":
        return ids.note(track, item["at"], root, have)
    if kind == "hit":
        return ids.hit(track, item["drum"], item["at"], root, have)
    return ids.clip(track, item["at"], root, have)


def _free_group(ctx, group):
    have = {c.get("group") for i in ctx.idx.values() for c in [i.item] if c.get("type") == "clip"}
    n = 2
    while f"{group} {n}" in have:
        n += 1
    return f"{group} {n}"


def _register(kind):
    label, key = LABELS[kind], KINDS[kind]

    @REGISTRY.operation(f"{kind}.move", f"Move {label}s later or earlier by an amount (seconds or beats); each time "
                        "keeps the way it was written.", target=kind, params=[BY_REQUIRED], label=f"Move {label}")
    def move(ctx, targets, args):
        every = _with_group(ctx, targets, kind)
        plan = [(t, moved(ctx, ctx.item(t), args["by"])) for t in every]   # all from the start state, then set
        for t, at in plan:
            ctx.set(t, "at", at)

    @REGISTRY.operation(f"{kind}.duplicate", f"Copy {label}s: the copies sit `by` later (default: right after the "
                        "selection's end), with new ids.", target=kind, params=[BY], label=f"Duplicate {label}")
    def duplicate(ctx, targets, args):
        root = ctx.doc
        items = [ctx.item(t) for t in _with_group(ctx, targets, kind)]
        first = min(start_of(root, i) for i in items)
        by = args["by"] if "by" in args else max(end_of(root, i) for i in items) - first
        if "by" not in args and by <= 1e-6:
            ctx.fail(codes.BAD_ARGUMENT, "by", f"can't be worked out: the selected {label}s have no length",
                     hint="Give `by` (seconds or beats).")
        renamed_groups: dict = {}
        for item in items:
            track = ctx.idx[item["id"]].parent
            at = moved(ctx, item, by)
            new = copy.deepcopy(item)
            new["at"] = at
            new["id"] = _new_id(kind, track, new, ctx)
            if kind == "clip":
                if new.get("group"):                    # a copied layer is its own layer, not a member of the old one
                    new["group"] = renamed_groups.setdefault(new["group"], _free_group(ctx, new["group"]))
                used = taken(ctx) | {new["id"]}
                for e in new.get("effects", []):
                    e["id"] = ids.effect(new["id"], e.get("effect", "effect"), used)
                    used.add(e["id"])
            ctx.insert(track, key, new)


for _kind in LABELS:
    _register(_kind)
