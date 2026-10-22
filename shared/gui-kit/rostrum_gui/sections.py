"""The settings panel by importance (opt-in: a bridge with `sections = True`), built from each param's `importance`
and `group` only, never per kind:
- **Essentials**: the `primary` params in data order, no headings; a small gap (label "") where the group changes.
- **Every other group folded to its name**: one fold row per group with a non-primary param, then its `secondary`
  and `deep` params (rank, then data order), shown only while the group is open. A group whose first such param
  has the group's own name ("Outline" › Outline) has no separate fold row: that param's row carries the fold
  (chevron + its own widget), so no heading is said twice.
- **Search**: a separate layout, every param under its group's heading (`rows.layout`'s heading rules, deep params
  included); `rows.evaluate(query=...)` keeps only valid params that `rows.matches` the search.
Param rows carry `in`: "" (shown when valid) or the fold's group (shown when valid and that group is open).
"""
from __future__ import annotations

from itertools import takewhile

from .rows import RANK, _grouped, _param_row


def layout(op, kind: str = "") -> list[dict]:
    """Essentials, then one fold per other group (static: the same rows for every item of a kind)."""
    if op is None:
        return []
    params = [p for p in op.params if p.type != "id"]
    essentials = [p for p in params if p.importance == "primary"]
    rest = [p for p in params if p.importance != "primary"]
    rows: list[dict] = []
    for i, p in enumerate(essentials):
        if i and p.group != essentials[i - 1].group:     # a gap where the group changes, never a heading
            run = takewhile(lambda q: q.group == p.group, essentials[i:])
            rows.append({"row": "group", "id": "gap:" + p.name, "label": "", "members": [q.name for q in run]})
        rows.append({**_param_row(p), "in": ""})
    if essentials and rest:
        rows.append({"row": "group", "id": "gap:folds", "label": "", "members": [p.name for p in rest], "by": "holds"})
    for g in dict.fromkeys(p.group for p in rest):
        members = sorted((p for p in rest if p.group == g), key=lambda p: RANK[p.importance])    # stable
        head = members[0] if members[0].label.lower() == g.lower() else None
        inside = members[1:] if head else members
        if head:
            rows.append({**_param_row(head), "in": "", "fold": g, "members": [p.name for p in inside]})
        else:
            rows.append({"row": "fold", "id": "fold:" + g, "label": g, "fold": g, "members": [p.name for p in inside]})
        rows += [{**_param_row(p), "in": g} for p in inside]
    return rows


def search_layout(op, kind: str = "") -> list[dict]:
    """Every param under its group's heading, for a search (what shows is decided by `rows.matches`)."""
    if op is None:
        return []
    return [{**r, "in": ""} if r["row"] == "param" else r for r in _grouped([p for p in op.params if p.type != "id"], kind)]

