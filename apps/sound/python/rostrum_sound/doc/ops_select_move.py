"""Move and copy the selected notes, drum hits and clips: `<kind>.move` (nudge, paste at an offset) and
`<kind>.duplicate` (copies placed `by` an amount, default right after the selection's end; `times` / `until`: repeat.py). One maker per kind.
A layered clip's group moves with it (like `clip.set at`). New ids of a copy: `select_time.inserted(change)`.
"""
from __future__ import annotations

import copy

from rostrum_core import codes

from . import ids, repeat
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


def _uniform(ctx, every, by):
    """(ids, path, amount): the items whose time moves by the very same number in the way it is written (a time in
    beats moved by beats, one in seconds moved by seconds), so the move is one `Shift`; the rest are set one by one."""
    beats = isinstance(by, dict)
    path, d = (["at", "beat"], float(by["beats"])) if beats else (["at"], float(by))
    even, idx = [], ctx.idx                 # (targets and their group mates: checked, all in the index)
    for t in every:
        at = idx[t].item["at"]
        v = at.get("beat") if beats and type(at) is dict and len(at) == 1 else at if not beats else None
        if (type(v) is float or type(v) is int) and v + d >= 0:
            even.append(t)
    return even, path, d


def _register(kind):
    label, key = LABELS[kind], KINDS[kind]

    @REGISTRY.operation(f"{kind}.move", f"Move {label}s later or earlier by an amount (seconds or beats); each time "
                        "keeps the way it was written.", target=kind, params=[BY_REQUIRED], label=f"Move {label}")
    def move(ctx, targets, args):
        every = _with_group(ctx, targets, kind)
        even, path, d = _uniform(ctx, every, args["by"])                    # one edit for every time written alike
        alike = set(even)                   # (a list: each of 3,352 notes looked up in 3,352 ids, ~30 ms a Right)
        plan = [(t, moved(ctx, ctx.item(t), args["by"])) for t in every if t not in alike]   # from the start state
        ctx.shift(even, path, d, 4)
        for t, at in plan:
            ctx.set(t, "at", at)

    @REGISTRY.operation(f"{kind}.duplicate", f"Copy {label}s: the copies sit `by` later (default: right after the "
                        f"selection's end), with new ids. `times` (1 … 64) makes that many copies in a row; `until` (a time, "
                        f'"#marker" or {{"section": "verse"}}) copies as many as fit before that point and cuts the last at it '
                        f"({'notes shortened' if kind == 'note' else 'clips shortened' if kind == 'clip' else 'hits past it left out'}). "
                        "One call, one undo step.", target=kind, params=[BY, repeat.TIMES, repeat.UNTIL],
                        label=f"Duplicate {label}")
    def duplicate(ctx, targets, args):
        root = ctx.doc
        items = [ctx.item(t) for t in _with_group(ctx, targets, kind)]
        first = min(start_of(root, i) for i in items)
        by = args["by"] if "by" in args else max(end_of(root, i) for i in items) - first
        if "by" not in args and by <= 1e-6:
            ctx.fail(codes.BAD_ARGUMENT, "by", f"can't be worked out: the selected {label}s have no length",
                     hint="Give `by` (seconds or beats).")
        n, point = repeat.count(ctx, first, by, args)
        plan = [(item, ctx.idx[item["id"]].parent, moved(ctx, item, repeat.scaled(by, k)), k)   # all from the start state
                for k in range(1, n + 1) for item in items]
        renamed_groups: dict = {}
        for item, track, at, k in plan:
            new = copy.deepcopy(item) if kind == "clip" else dict(item)   # the insert copies it whole; a clip: effects renamed below
            new["at"] = at
            if point is not None:                       # `until`: cut at the point (its end moved with the copy)
                new = repeat.cut(ctx, kind, new, end_of(root, item) + start_of(root, new) - start_of(root, item), point)
                if new is None:
                    continue
            new["id"] = _new_id(kind, track, new, ctx)
            if kind == "clip":
                if new.get("group"):                    # a copied layer is its own layer, not a member of the old one
                    new["group"] = renamed_groups.setdefault((new["group"], k), _free_group(ctx, new["group"]))
                used = taken(ctx) | {new["id"]}
                for e in new.get("effects", []):
                    e["id"] = ids.effect(new["id"], e.get("effect", "effect"), used)
                    used.add(e["id"])
            ctx.insert(track, key, new)


for _kind in LABELS:
    _register(_kind)
