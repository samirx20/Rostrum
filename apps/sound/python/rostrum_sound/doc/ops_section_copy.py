"""`section.duplicate`: a copy of a section and everything that starts inside it (notes, drum hits, clips, designed
sounds on every track), placed right after it: the copy section starts where the original ends. One operation, one
undo step; nothing after the section moves (the copy sits on top of what is there, as Ctrl+D does for items).
"""
from __future__ import annotations

import copy

from . import ids
from .ops_select_move import _new_id
from .registry import REGISTRY, taken
from .select_time import moved, start_of

KINDS = {"notes": "note", "hits": "hit", "clips": "clip", "sounds": "sound"}


@REGISTRY.operation("section.duplicate", "Copy sections with everything that starts inside them to right after "
                    "each (the copy is named like it, with a number); one step.", target="section",
                    label="Duplicate section")
def duplicate(ctx, targets, args):
    root = ctx.doc
    for t in targets:
        s = ctx.item(t)
        a, b = start_of(root, s), start_of(root, {**s, "at": s["end"], "id": t})
        by = round(b - a, 6)
        inside = [(tr["id"], key, it) for tr in root.get("tracks", []) for key in KINDS for it in tr.get(key, [])
                  if a - 1e-6 <= start_of(root, it) < b - 1e-6]
        for track, key, it in inside:
            new = copy.deepcopy(it)
            new["at"] = moved(ctx, it, by)
            if KINDS[key] == "sound":
                new["id"] = ids.sound(track, it["design"], new["at"], root, taken(ctx))
            else:
                new["id"] = _new_id(KINDS[key], track, new, ctx)
            for fx in new.get("effects", []):
                fx["id"] = ids.effect(new["id"], fx.get("effect", "effect"), taken(ctx) | {new["id"]})
            ctx.insert(track, key, new)
        names = {x.get("name") for x in root.get("sections", [])}
        n = 2
        while f"{s['name']}_{n}" in names:
            n += 1
        name = f"{s['name']}_{n}"
        copy_ = {**copy.deepcopy(s), "id": f"section.{name}", "name": name, "at": moved(ctx, s, by),
                 "end": moved(ctx, {**s, "at": s["end"]}, by)}
        ctx.insert("root", "sections", copy_, ctx.idx[t].index + 1)
