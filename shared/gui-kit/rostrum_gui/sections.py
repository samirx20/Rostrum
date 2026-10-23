"""The settings panel by importance (opt-in: a bridge with `sections = True`), built from each param's `importance`
and `group` only, never per kind:
- **Essentials**: the `primary` params in data order, no headings; a small gap (label "") where the group changes.
- **A group that has essentials is never named again**: its other params (the ones that apply) follow its essentials
  in place, so no name in the row of names repeats a setting already shown ("Shape", "Fill").
- **Every other group by name**: one fold row per group with a non-primary param, then its `secondary` and `deep`
  params (rank, then data order). A kind's own group (`OWN`) is always open. Only an OPEN group shows (its fold row is its heading, a click folds it); a group
  with a value changed from its default is open until the person folds it (you see what you changed).
- **One row of names** last (row "folds"): every group that applies to this item and is folded, "Depth · Timing ·
  Blend"; a click on a name opens that group just above it. A group with nothing that applies is not named at all.
- **Search**: a separate layout, every param under its group's heading (`rows.layout`'s heading rules, deep params
  included); `rows.evaluate(query=...)` keeps only valid params that `rows.matches` the search.
Param rows carry `in`: "" (shown when valid) or the fold's group (shown when valid and that group is open).
"""
from __future__ import annotations

from itertools import takewhile

from .pairs import pair_up
from .rows import RANK, _grouped, _param_row

# What a folded group is CALLED on screen when its own name would echo an essential row above it: {(kind, group): words}
# (kind lower-case). An app fills it once (2D: "Font" under Text reads "More type"). The group's key never changes:
# open / folded choices, `reveal`, `fold:<group>` steps and guides keep using it; only the heading and the name change.
WORDS: dict[tuple[str, str], str] = {}

# The group a kind IS (a light's "Light", a camera's "Lens"): {kind: group} (kind lower-case). Its fold row is always open
# (no chevron, no folding): the thing itself never hides behind a click. Every other group follows the changed rule.
# An app fills it once; with none (2D) every group opens only when changed.
OWN: dict[str, str] = {}


def layout(op, kind: str = "") -> list[dict]:
    """Essentials, then one fold per other group (static: the same rows for every item of a kind)."""
    if op is None:
        return []
    params = [p for p in op.params if p.type != "id"]
    shown = {p.group for p in params if p.importance == "primary"}      # a group with an essential is shown whole, in place
    essentials = [p for p in params if p.importance == "primary" or p.group in shown]
    order = list(dict.fromkeys(p.group for p in essentials))
    essentials.sort(key=lambda p: (order.index(p.group), RANK[p.importance]))      # stable: data order inside
    rest = [p for p in params if p not in essentials]
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
        rows.append({"row": "fold", "id": "fold:" + g, "label": WORDS.get((kind.lower(), g), g), "fold": g, "members": [p.name for p in members],
                     "own": OWN.get(kind.lower()) == g})
        rows += [{**_param_row(p), "in": g} for p in members]
    if rest:
        rows.append({"row": "folds", "id": "folds", "label": "", "members": [p.name for p in rest]})
    return pair_up(rows)


def search_layout(op, kind: str = "") -> list[dict]:
    """Every param under its group's heading, for a search (what shows is decided by `rows.matches`)."""
    if op is None:
        return []
    return pair_up([{**r, "in": ""} if r["row"] == "param" else r
                    for r in _grouped([p for p in op.params if p.type != "id"], kind)])

