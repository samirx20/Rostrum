"""Old files: a hugging auto-layout group used to grow around its anchor (the middle), and now keeps its top-left
fixed (`hugPin`, layout.py `hugged`). A file written before the field existed has no `hugPin` on its groups, so
each of its hugging groups is set to `hugPin` off: it draws exactly as it did, and the person can turn it on. Hugging
is now on by default (as in Figma), so an old laid-out group with no size mode of its own (`sizeW` / `sizeH`, once
`hugWidth` / `hugHeight`: migrations.py) gets "fixed";
padding now starts at 10 px (Figma's), so one with no `padding` of its own keeps 0.
Run once on open (rostrum_core DocKind.upgrade), recorded as one change."""
from __future__ import annotations

import copy


def upgrade(data: dict, lists: dict):
    """(new data, label) with `hugPin` off on every old hugging group, or None when there is none."""
    from rostrum_core.tree import walk
    if not any(g.get("type") == "group" and g.get("layout", "none") != "none" and not {"hugPin", "sizeW", "sizeH", "padding"} <= g.keys()
               for g in walk(data, lists)):          # nothing old: no copy of a big document
        return None
    work = copy.deepcopy(data)
    old = [g for g in walk(work, lists) if g.get("type") == "group" and g.get("layout", "none") != "none"
           and "fit" in (g.get("sizeW"), g.get("sizeH")) and "hugPin" not in g]
    for g in old:
        g["hugPin"] = False
    unset = [g for g in walk(work, lists) if g.get("type") == "group" and g.get("layout", "none") != "none"
             and ("sizeW" not in g or "sizeH" not in g or "padding" not in g)]
    for g in unset:
        g.setdefault("sizeW", "fixed")
        g.setdefault("sizeH", "fixed")
        g.setdefault("padding", 0.0)
    if unset and not old:
        return work, f"Auto-layout group{'s' * (len(unset) > 1)} keep{'s' * (len(unset) == 1)} their own size"
    return (work, f"Hugging group{'s' * (len(old) > 1)} keep{'s' * (len(old) == 1)} growing around the anchor") if old else None
