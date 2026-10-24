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
from .pairs import pair_up, pair_valid

RANK = {"primary": 0, "secondary": 1, "deep": 2}
ROLES = ("row", "id", "label", "type", "group", "importance", "help", "options", "min", "max", "step", "unit", "display",
         "valid", "value", "anim", "words", "expr", "item", "minItems", "maxItems", "control", "filters", "fold", "open", "mixed", "default", "half", "letter", "more", "names", "own", "switch", "tag", "tagHelp", "note", "button")
# more: "" for most rows; a choice whose list can grow names the last entry that adds one ("Load picture…"):
# picking it opens a file dialog (filters) and calls bridge.loadChoice(id, path).
# anim: "" (can't be animated), "still" (could be), "keyed" (has keys), "onkey" (has a key at the playhead).
# expr: "" for most rows; a param driven by an expression or binding has {"text", "note"}: the row shows them (and a
# way to clear it) instead of its widget.
# A "list" param (item, minItems, maxItems): `options` are what may be added — its own choices for a list of choices,
# else what the app's `choices(name)` gives (e.g. the tracks a duck may dip under), [{value, label}].
# A "pick" param (control "pick", a text naming one of a list the app knows) shows as a choice: what the app's
# `choices(name)` gives (e.g. the layers a track matte may use, the fonts there are: an option may carry `face`, the font
# family its label is drawn in, and `section`, a heading over each run of options sharing it), after "None" when "" is allowed (its default is "": the label is its words for "", e.g.
# "Main mix"). Never a bare text box of ids or names; with nothing to pick (and nothing picked) the row is absent.
# tag, tagHelp: optional (an app adds them to a param row): a small word after the label and its hover sentence.
# note: optional (an app adds it to a param row): {"text", "kind": "hint" | "warning"}, a short line under the field. Absent
# (None) when there is nothing to say: no gap is left. Worked out live from the document, like every other row value.
# button: optional (an app adds it from its actions, action_views.row_buttons): {"label", "id", "menu": [{value, label}]}, a
# small button (or a menu when `menu` has entries) at the right of the field; a click runs the action through bridge.rowAction(id).
# own: a fold row of the kind's own group (sections.OWN): always open, never folded.
# switch: a fold row's param that turns its group on ("" = none, sections.switch_of), with `on` / `off` its values: the
# group is open exactly while it is not `off`; its name in "folds" adds it (sets `on`) and its heading's remove control
# sets `off`. A toggle's own row (marked `switches`) is never shown there; a number's is (it is the amount).
# shown (a param's, Param.shown): "script" = never on a screen; "changed" = only while away from its default.
# fold: the group a fold row opens; open: that group is open now (None when nothing inside applies: the row is absent).
# names: the "folds" row's folded groups that apply, [{"group", "label", "changed", "switch"}] in panel order (sections.py).
# mixed: several items selected and their values differ (the widget says "Mixed"; many.py).
# display: how a number shows ("percent", "db", "pan"; "" = plain), ValueKinds.js; amounts get a slider too.
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
    return pair_up(rows)


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
            "step": p.step, "unit": p.unit, "display": p.display, "valid_when": p.valid_when, "default": p.default,
            "words": [{"value": v, "label": w} for v, w in p.words.items()],
            "item": p.item or "", "minItems": p.min_items, "maxItems": p.max_items, "control": p.control,
            "filters": list(p.filters), "shown": p.shown}


def evaluate(static: list[dict], item: dict, facts: dict, more_open: bool, anim=None, expr=None, choices=None,
             opened=(), query: str = "", elsewhere=frozenset(), starts=None) -> list[dict]:
    """The rows with `valid`, `value`, `anim` and `expr` filled in for these values (`item`: the item's values as
    the screen shows them, e.g. at the playhead). `anim(name)` gives a param's key state; none: no keys.
    `expr(name)` gives {"text", "note"} for a param driven by an expression or binding; none: no param is.
    Rows with `in` (sections.py): `opened` is the person's choice per group ({name: open?}; a set = those open); a
    group with no choice is open when a value in it differs from its default and from `starts` (the values this kind
    may start with instead, bridge.starts: a text placed by the Text tool starts at its top-left). A non-blank `query` keeps only matches.
    `elsewhere`: params the screen shows in another place (bridge.on_page); here they count as not applying, so a
    group is never opened or named for them alone."""
    picks = {r["id"]: choices(r["id"]) if choices else [] for r in static if r.get("control") == "pick"}
    ok = {r["id"]: holds(r["valid_when"], item, facts) and _shown(r, item) and (r["id"] not in picks or bool(picks[r["id"]])
                                                                                or bool(item.get(r["id"], r["default"])))
          for r in static if r["row"] == "param"}
    ok.update(dict.fromkeys(set(elsewhere) & ok.keys(), False))
    opened = _open_groups(static, item, ok, opened, starts or {})
    out = []
    for r in static:
        r = dict(r)
        if "fold" in r:
            r["open"] = r["fold"] in opened if any(ok[m] for m in r["members"]) else None
        if r["row"] == "folds":
            r["names"] = [{"group": f["fold"], "label": f["label"], "changed": f["fold"] in opened.changed,
                           "switch": f.get("switch", "")} for f in static
                          if "fold" in f and f["fold"] not in opened and any(ok[m] for m in f["members"])]
        if r["row"] == "param":
            r["value"] = item.get(r["id"], r["default"])
            r["anim"] = anim(r["id"]) if anim else ""
            r["expr"] = expr(r["id"]) if expr else ""
            if r["type"] == "list" and r["item"] != "choice":
                r["options"] = choices(r["id"]) if choices else []
            if r["id"] in picks:
                r["type"], r["control"] = "choice", ""
                none = [{"value": "", "label": next((w["label"] for w in r["words"] if w["value"] == ""), "None")}]
                r["options"] = (none if r["default"] == "" else []) + picks[r["id"]]
            r["holds"] = ok[r["id"]]
            r["valid"] = ok[r["id"]] and _open(r, more_open, opened, query) and "switches" not in r
        else:
            r["value"], r["anim"], r["expr"] = None, "", ""
            r["holds"] = any(ok[m] for m in r["members"])
        out.append(r)
    pair_valid(out, item)
    return _headers(out)


def _shown(r: dict, item: dict) -> bool:
    """A param's own screen rule (Param.shown): never for script data, only while changed for a "changed" one."""
    rule = r.get("shown", "")
    return rule != "script" and (rule != "changed" or item.get(r["id"], r["default"]) != r["default"])


class _Opened(set):
    """The open groups (a set), plus `changed`: the groups holding a value away from its default."""
    changed: set


def _open_groups(static, item, ok, choice, starts) -> _Opened:
    """Which groups are open: the person's choice, else open when changed (a value that applies, at neither its
    default nor the kind's own start)."""
    choice = choice if isinstance(choice, dict) else {g: True for g in choice}
    params = {r["id"]: r for r in static if r["row"] == "param"}
    out = _Opened()
    out.changed = set()
    for f in (r for r in static if "fold" in r):
        if any(ok[m] and params[m]["default"] is not None
               and item.get(m, params[m]["default"]) not in (params[m]["default"], starts.get(m, params[m]["default"]))
               for m in f["members"]):
            out.changed.add(f["fold"])
        sw = f.get("switch")
        if (item.get(sw, params[sw]["default"]) != f["off"] and ok[sw]) if sw else f.get("own") or choice.get(f["fold"], f["fold"] in out.changed):
            out.add(f["fold"])
    return out


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
        elif r["row"] == "folds":
            r["valid"] = bool(r["names"])
        elif "fold" in r:                  # a group's heading shows only while it is open (folded: a name in "folds")
            r["valid"] = r["holds"] and bool(r["open"])
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
    went goes too. A group left with ONE of several members gives up its heading and joins the group above (a
    heading over a lone leftover reads wrong: "Mix" over just "Tone"); with no group above it just loses the heading."""
    if not gone:
        return rows
    kept = [r for r in rows if not (r["row"] == "param" and r["id"] in gone)]
    holds = {r["id"]: r["holds"] for r in kept if r["row"] == "param"}
    left = {id(r): [m for m in r.get("members", []) if m in holds] for r in kept if r["row"] != "param"}
    join, above = {}, None             # lone param id -> the group (row) it joins
    for r in kept:
        if r["row"] != "group" or r.get("by") == "holds" or not left[id(r)]:
            continue
        if len(left[id(r)]) == 1 and len(r.get("members", [])) > 1:
            join[left[id(r)][0]] = above
        else:
            above = r["id"]
    out = []
    for r in kept:
        if r["row"] == "param":
            if r["id"] in join and join[r["id"]]:
                r = {**r, "group": join[r["id"]][6:]}
            out.append(r)
            continue
        members = left[id(r)]
        if not members:
            continue
        if members[0] in join and len(members) == 1 and r["row"] == "group":
            continue                   # the heading goes; its lone member stays
        members = members + [j for j, g in join.items() if g == r["id"]]
        out.append({**r, "members": members, "holds": any(holds[m] for m in members)})
    return _headers(out)
