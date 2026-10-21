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
         "valid", "value", "anim", "words", "expr", "item", "minItems", "maxItems", "control")
# anim: "" (can't be animated), "still" (could be), "keyed" (has keys), "onkey" (has a key at the playhead).
# expr: "" for most rows; a param driven by an expression or binding has {"text", "note"}: the row shows them (and a
# way to clear it) instead of its widget.
# A "list" param (item, minItems, maxItems): `options` are what may be added — its own choices for a list of choices,
# else what the app's `choices(name)` gives (e.g. the tracks a duck may dip under), [{value, label}].
# A "pick" param (control "pick", a text naming one other item, "" = none) shows as a choice: "None" first, then what
# the app's `choices(name)` gives (e.g. the layers a track matte may use). Never a bare text box of ids; with nothing
# to pick (and nothing picked) the row is absent.


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
            "importance": p.importance, "help": p.help, "options": p.choices(), "min": p.min, "max": p.max,
            "step": p.step, "unit": p.unit, "valid_when": p.valid_when, "default": p.default,
            "words": [{"value": v, "label": w} for v, w in p.words.items()],
            "item": p.item or "", "minItems": p.min_items, "maxItems": p.max_items, "control": p.control}


def evaluate(static: list[dict], item: dict, facts: dict, more_open: bool, anim=None, expr=None, choices=None) -> list[dict]:
    """The rows with `valid`, `value`, `anim` and `expr` filled in for these values (`item`: the item's values as
    the screen shows them, e.g. at the playhead). `anim(name)` gives a param's key state; none: no keys.
    `expr(name)` gives {"text", "note"} for a param driven by an expression or binding; none: no param is."""
    picks = {r["id"]: choices(r["id"]) if choices else [] for r in static if r.get("control") == "pick"}
    ok = {r["id"]: holds(r["valid_when"], item, facts) and (r["id"] not in picks or bool(picks[r["id"]])
                                                            or bool(item.get(r["id"], r["default"])))
          for r in static if r["row"] == "param"}
    out = []
    for r in static:
        r = dict(r)
        if r["row"] == "param":
            r["value"] = item.get(r["id"], r["default"])
            r["anim"] = anim(r["id"]) if anim else ""
            r["expr"] = expr(r["id"]) if expr else ""
            if r["type"] == "list" and r["item"] != "choice":
                r["options"] = choices(r["id"]) if choices else []
            if r["id"] in picks:
                r["type"], r["control"] = "choice", ""
                r["options"] = [{"value": "", "label": "None"}] + picks[r["id"]]
            r["holds"] = ok[r["id"]]
            r["valid"] = ok[r["id"]] and (r["importance"] != "deep" or more_open)
        else:
            r["value"], r["anim"], r["expr"] = None, "", ""
            r["holds"] = r["valid"] = any(ok[m] for m in r["members"])
        out.append(r)
    return out


def shown(rows: list[dict]) -> tuple[list[str], list[str]]:
    """(on screen, behind More): the names of the valid params, in screen order. For screenshots and agents."""
    return ([r["id"] for r in rows if r["row"] == "param" and r["importance"] != "deep" and r["valid"]],
            [r["id"] for r in rows if r["row"] == "param" and r["importance"] == "deep" and r["holds"]])


def omit(rows: list[dict], gone: set[str]) -> list[dict]:
    """The evaluated rows without the params in `gone` (shown elsewhere on the page); a group whose members all
    went goes too."""
    if not gone:
        return rows
    kept = [r for r in rows if not (r["row"] == "param" and r["id"] in gone)]
    holds = {r["id"]: r["holds"] for r in kept if r["row"] == "param"}
    out = []
    for r in kept:
        if r["row"] != "param":
            members = [m for m in r.get("members", []) if m in holds]
            if not members:
                continue
            r = {**r, "members": members}
            r["holds"] = r["valid"] = any(holds[m] for m in members)
        out.append(r)
    return out
