"""The inspector's rows for one item, built from its kind's field operation (the rule of individuality as data).

Layout (fixed per kind, so delegates live on and animate): for each group, in the order groups first appear
among the non-deep params, a group header and its params (primary before secondary, then data order); then a
More row and the deep params in data order. Each row then gets `valid`:
- a param: its valid_when holds on the item's values and facts (and, if deep, More is open);
- a group header: any of its members is valid (an empty group is absent, not an empty header);
- the More row: any deep param is valid.
Rows that are not valid are absent on screen (they collapse to zero height); nothing is greyed.
"""
from __future__ import annotations

from rostrum_core.conditions import holds

RANK = {"primary": 0, "secondary": 1, "deep": 2}
ROLES = ("row", "id", "label", "type", "group", "importance", "help", "options", "min", "max", "step", "unit",
         "valid", "value", "anim")
# anim: "" (can't be animated), "still" (could be), "keyed" (has keys), "onkey" (has a key at the playhead).


def layout(op) -> list[dict]:
    """The static row list for a field operation: group headers, params, More, deep params."""
    if op is None:
        return []
    shown = [p for p in op.params if p.importance != "deep" and p.type != "id"]
    deep = [p for p in op.params if p.importance == "deep" and p.type != "id"]
    groups = list(dict.fromkeys(p.group for p in shown))
    rows: list[dict] = []
    for g in groups:
        members = sorted((p for p in shown if p.group == g), key=lambda p: RANK[p.importance])  # stable
        rows.append({"row": "group", "id": "group:" + g, "label": g, "members": [p.name for p in members]})
        rows += [_param_row(p) for p in members]
    if deep:
        rows.append({"row": "more", "id": "more", "label": "More", "members": [p.name for p in deep]})
        rows += [_param_row(p) for p in deep]
    return rows


def _param_row(p) -> dict:
    return {"row": "param", "id": p.name, "label": p.label, "type": p.type, "group": p.group,
            "importance": p.importance, "help": p.help, "options": list(p.options), "min": p.min, "max": p.max,
            "step": p.step, "unit": p.unit, "valid_when": p.valid_when, "default": p.default}


def evaluate(static: list[dict], item: dict, facts: dict, more_open: bool, anim=None) -> list[dict]:
    """The rows with `valid`, `value` and `anim` filled in for these values (`item`: the item's values as the
    screen shows them, e.g. at the playhead). `anim(name)` gives a param's key state; none: no keys."""
    ok = {r["id"]: holds(r["valid_when"], item, facts) for r in static if r["row"] == "param"}
    out = []
    for r in static:
        r = dict(r)
        if r["row"] == "param":
            r["value"] = item.get(r["id"], r["default"])
            r["anim"] = anim(r["id"]) if anim else ""
            r["holds"] = ok[r["id"]]
            r["valid"] = ok[r["id"]] and (r["importance"] != "deep" or more_open)
        else:
            r["value"], r["anim"] = None, ""
            r["holds"] = r["valid"] = any(ok[m] for m in r["members"])
        out.append(r)
    return out


def shown(rows: list[dict]) -> tuple[list[str], list[str]]:
    """(on screen, behind More): the names of the valid params, in screen order. For screenshots and agents."""
    return ([r["id"] for r in rows if r["row"] == "param" and r["importance"] != "deep" and r["valid"]],
            [r["id"] for r in rows if r["row"] == "param" and r["importance"] == "deep" and r["holds"]])
