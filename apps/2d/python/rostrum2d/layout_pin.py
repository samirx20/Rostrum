"""Old files: a hugging auto-layout group used to grow around its anchor (the middle), and now keeps its top-left
fixed (`hugPin`, layout.py `hugged`). A file written before the field existed has no `hugPin` on its groups, so
each of its hugging groups is set to `hugPin` off: it draws exactly as it did, and the person can turn it on. Run once
on open (rostrum_core DocKind.upgrade), recorded as one change."""
from __future__ import annotations

import copy


def upgrade(data: dict, lists: dict):
    """(new data, label) with `hugPin` off on every old hugging group, or None when there is none."""
    from rostrum_core.tree import walk
    work = copy.deepcopy(data)
    old = [g for g in walk(work, lists) if g.get("type") == "group" and g.get("layout", "none") != "none"
           and (g.get("hugWidth") or g.get("hugHeight")) and "hugPin" not in g]
    for g in old:
        g["hugPin"] = False
    return (work, f"Hugging group{'s' * (len(old) > 1)} keep{'s' * (len(old) == 1)} growing around the anchor") if old else None
