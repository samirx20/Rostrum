"""Several items selected: the settings they all share, as one list of rows (no Qt).

- Same kind: all its params. Mixed kinds: the params every kind's field operation has, by name and type (in the
  first item's order, with the first item's labels and groups).
- A row's state is the AND of each item's: a param shows only while it applies to every selected item. A value that
  differs is `mixed` (the widget says "Mixed"; number, text, choice, colour, toggle). What can't be shown "mixed" —
  an expression or binding, a pick, a list, a curve, a file — is absent when the items differ.
- The key mark: "onkey" / "keyed" when every item is; else "still" when any could be animated ("" when one can't).
Each item's own rows come from rows.evaluate (and rows.omit) as for one item; `merge` folds them together.
"""
from __future__ import annotations

from types import SimpleNamespace

from .rows import _headers

SAME_ONLY = ("list",)                       # types shown only when every item has the same value
SAME_ONLY_CONTROLS = ("pick", "curve", "file", "folder")


def shared_op(ops: list):
    """The field operation for these items' kinds: the one op when it is the same, else the params all of them have
    (name and type). None when any kind has no settings."""
    if any(op is None for op in ops):
        return None
    if all(op is ops[0] for op in ops):
        return ops[0]
    kinds = [{p.name: p.type for p in op.params} for op in ops[1:]]
    return SimpleNamespace(params=[p for p in ops[0].params if all(k.get(p.name) == p.type for k in kinds)])


def own_rules(static: list[dict], op) -> list[dict]:
    """Mixed kinds: the shared layout with THIS item's own rules for when a setting applies, and its own default. A
    text's X applies "while it doesn't follow a path"; a shape has no such field, so judging the shape by the text's
    rule hid X, Y, Scale and Rotation for a text and a shape selected together."""
    own = {p.name: p for p in op.params}
    return [{**r, "valid_when": own[r["id"]].valid_when, "default": own[r["id"]].default}
            if r["row"] == "param" and r["id"] in own else r for r in static]


def merge(each: list[list[dict]]) -> list[dict]:
    """One row list from each item's evaluated rows (all from one static layout; rows an item lacks are dropped)."""
    others = [{r["id"]: r for r in rows} for rows in each[1:]]
    out = []
    for r in each[0]:
        alike = [o.get(r["id"]) for o in others]
        if any(a is None for a in alike):
            continue
        out.append(_param(r, alike) if r["row"] == "param" else {**r, "mixed": False})
    holds = {r["id"]: r["holds"] for r in out if r["row"] == "param"}
    for r in out:
        if r["row"] != "param":
            r["holds"] = any(holds.get(m, False) for m in r["members"])
            if "open" in r:
                r["open"] = next((x["open"] for x in [r] + [o[r["id"]] for o in others] if x["open"] is not None), None)
    return _headers(out)


def _param(r: dict, alike: list[dict]) -> dict:
    rows = [r] + alike                       # this item first, then the others' same row
    mixed = any(a["value"] != r["value"] for a in alike)
    same_only = r["type"] in SAME_ONLY or r.get("control") in SAME_ONLY_CONTROLS
    exprs_differ = any(a["expr"] != r["expr"] for a in alike)
    ok = all(a["holds"] for a in rows) and not exprs_differ and not (mixed and (same_only or r["expr"]))
    anims = [a["anim"] for a in rows]
    anim = ("" if "" in anims else anims[0] if len(set(anims)) == 1 else
            "keyed" if all(a in ("keyed", "onkey") for a in anims) else "still")
    return {**r, "holds": ok, "valid": ok and all(a["valid"] for a in rows), "mixed": mixed, "anim": anim}
