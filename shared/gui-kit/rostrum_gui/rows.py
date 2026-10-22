"""The inspector's rows for one item, built from its kind's field operation (the rule of individuality as data).

Layout (fixed per kind, so delegates live on and animate): for each group, in the order groups first appear
among the non-deep params, a group header and its params (primary before secondary, then data order); then a
More row and the deep params in data order. A first group named as the item's own type has no header: the panel's
subtitle right above it already says that word (a key showed "Key" twice, a text "Text"). A group whose first row
has the group's own name ("Fill" › Fill, "Outline" › Outline) keeps its gap but shows no heading text (label ""): the
row right under it already says the word. Each row then gets `valid`:
- a param: its valid_when holds on the item's values and facts (and, if deep, More is open);
- a group header: any of its members is valid (an empty group is absent, not an empty header);
- the More row: any deep param is valid.
Rows that are not valid are absent on screen (they collapse to zero height); nothing is greyed.
The settings panel by importance (essentials, folded groups, search) is sections.py; its rows carry `in` (and a
fold row `fold` / `open`), and the rules for those are here too.
"""
from __future__ import annotations

from rostrum_core.conditions import holds

from .match import starts

RANK = {"primary": 0, "secondary": 1, "deep": 2}
ROLES = ("row", "id", "label", "type", "group", "importance", "help", "options", "min", "max", "step", "unit",
         "valid", "value", "anim", "words", "expr", "item", "minItems", "maxItems", "control", "filters", "fold", "open", "mixed", "default")
# anim: "" (can't be animated), "still" (could be), "keyed" (has keys), "onkey" (has a key at the playhead).
# expr: "" for most rows; a param driven by an expression or binding has {"text", "note"}: the row shows them (and a
# way to clear it) instead of its widget.
# A "list" param (item, minItems, maxItems): `options` are what may be added — its own choices for a list of choices,
# else what the app's `choices(name)` gives (e.g. the tracks a duck may dip under), [{value, label}].
# A "pick" param (control "pick", a text naming one other item, "" = none) shows as a choice: "None" first, then what
# the app's `choices(name)` gives (e.g. the layers a track matte may use). Never a bare text box of ids; with nothing
# to pick (and nothing picked) the row is absent.
# fold: the group a fold row opens; open: that group is open now (None when nothing inside applies: the row is absent).
# mixed: several items selected and their values differ (the widget says "Mixed"; many.py).
# default: the param's own default (None = none: no reset); a number field puts itself back to it on a double-click.


def layout(op, kind: str = "") -> list[dict]:
    """The static row list for a field operation: group headers, params, More, deep params. `kind`: the item's
    type as the panel's subtitle shows it (none: every group has its header)."""
    if op is None:
        return []
    shown = [p for p in op.params if p.importance != "deep" and p.type != "id"]
    deep = [p for p in op.params if p.importance == "deep" and p.type != "id"]
    rows = _grouped(shown, kind)
    if deep:
        rows.append({"row": "more", "id": "more", "label": "More", "members": [p.name for p in deep]})
        rows += [_param_row(p) for p in deep]
    return rows


def _grouped(params, kind: str) -> list[dict]:
    """Each group's header (the heading rules above) and its params, primary before secondary, then data order."""
    rows: list[dict] = []
    for i, g in enumerate(dict.fromkeys(p.group for p in params)):
        members = sorted((p for p in params if p.group == g), key=lambda p: RANK[p.importance])  # stable
        if not (i == 0 and g.lower() == kind.lower()):
            said = members[0].label.lower() == g.lower()          # the first row already names the group
            rows.append({"row": "group", "id": "group:" + g, "label": "" if said else g,
                         "members": [p.name for p in members]})
        rows += [_param_row(p) for p in members]
    return rows


def _param_row(p) -> dict:
    return {"row": "param", "id": p.name, "label": p.label, "type": p.type, "group": p.group,
            "importance": p.importance, "help": p.help, "options": p.choices(), "min": p.min, "max": p.max,
            "step": p.step, "unit": p.unit, "valid_when": p.valid_when, "default": p.default,
            "words": [{"value": v, "label": w} for v, w in p.words.items()],
            "item": p.item or "", "minItems": p.min_items, "maxItems": p.max_items, "control": p.control,
            "filters": list(p.filters)}


def evaluate(static: list[dict], item: dict, facts: dict, more_open: bool, anim=None, expr=None, choices=None,
             opened=(), query: str = "") -> list[dict]:
    """The rows with `valid`, `value`, `anim` and `expr` filled in for these values (`item`: the item's values as
    the screen shows them, e.g. at the playhead). `anim(name)` gives a param's key state; none: no keys.
    `expr(name)` gives {"text", "note"} for a param driven by an expression or binding; none: no param is.
    Rows with `in` (sections.py): `opened` are the open groups' names; a non-blank `query` keeps only matches."""
    picks = {r["id"]: choices(r["id"]) if choices else [] for r in static if r.get("control") == "pick"}
    ok = {r["id"]: holds(r["valid_when"], item, facts) and (r["id"] not in picks or bool(picks[r["id"]])
                                                            or bool(item.get(r["id"], r["default"])))
          for r in static if r["row"] == "param"}
    out = []
    for r in static:
        r = dict(r)
        if "fold" in r:
            r["open"] = r["fold"] in opened if any(ok[m] for m in r["members"]) else None
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
            r["valid"] = ok[r["id"]] and _open(r, more_open, opened, query)
        else:
            r["value"], r["anim"], r["expr"] = None, "", ""
            r["holds"] = any(ok[m] for m in r["members"])
        out.append(r)
    return _headers(out)


def _open(r: dict, more_open: bool, opened, query: str) -> bool:
    """A param's own place is open: its fold (or More, for a deep param) is open, and it matches the search."""
    if "in" not in r:
        return r["importance"] != "deep" or more_open
    return (r["in"] == "" or r["in"] in opened) and (not query.strip() or matches(r, query))


def _headers(rows: list[dict]) -> list[dict]:
    """A heading or gap is there while any member is on screen; a More or fold row (and a gap marked `by: holds`)
    while any member applies, open or not."""
    on = {r["id"]: r["valid"] for r in rows if r["row"] == "param"}
    for r in rows:
        if r["row"] == "group" and r.get("by") != "holds":
            r["valid"] = any(on.get(m, False) for m in r["members"])
        elif r["row"] != "param":
            r["valid"] = r["holds"]
    return rows


def matches(row: dict, query: str) -> bool:
    """Every word of the search starts a word of the param's label, group or help (any case, any order):
    "op" finds Opacity, "move" finds a field whose help says "move it", never "remove"."""
    return starts(query.lower().split(), f"{row['label']} {row['group']} {row['help']}".lower())


def shown(rows: list[dict]) -> tuple[list[str], list[str]]:
    """(on screen, behind More): the names of the valid params, in screen order. For screenshots and agents.
    Rows by importance (sections.py): (on screen, folded away or hidden by the search) of the params that apply."""
    if any("in" in r for r in rows):
        params = [r for r in rows if r["row"] == "param"]
        return [r["id"] for r in params if r["valid"]], [r["id"] for r in params if r["holds"] and not r["valid"]]
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
            r["holds"] = any(holds[m] for m in members)
        out.append(r)
    return _headers(out)
