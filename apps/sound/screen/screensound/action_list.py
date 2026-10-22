"""The four doors of the action list (INTERACTION.md §1.2), from actions.py's entries: what applies now
(`available`), the context bar's buttons (`bar_items`), what folds under ⋯ (`overflow`), the right-click menu
(`menu_entries`), the empty-space menus (`at_menu`) and what a key says when its action doesn't apply (`why`). No Qt;
the kit's action list takes this over (INTERACTION.md Part 5, piece 1).
"""
from __future__ import annotations

from .action_calls import Facts
from .actions import ACTIONS

FOLD = 4                    # a bar button with more choices than this is one "… ▸" entry in a menu


def available(doc, ids, playhead=0.0, rng=None, clipboard=False, track="") -> list[dict]:
    """The valid actions in rank order (promoted ones first), each with its calls worked out; `importance` is
    "primary" (the bar) or "secondary" (⋯ and menus). `track`: the Editor's track (Delete on a range there)."""
    f = Facts(doc, ids, playhead, rng, clipboard, track)
    out = []
    for a in ACTIONS:
        if not a["valid_when"](f):
            continue
        cs = a["calls"](f) if a["calls"] else []
        if a["calls"] and not cs:
            continue
        promoted = a["promoted_when"] is not None and a["promoted_when"](f)
        label = a["label"](f) if callable(a["label"]) else a["label"]
        out.append({**{k: v for k, v in a.items() if k not in ("valid_when", "promoted_when", "calls")},
                    "label": label, "importance": "primary" if promoted else a["importance"],
                    "promoted": promoted, "calls": cs})
    return sorted(out, key=lambda a: (a["group"] == "edit", a["importance"] != "primary", not a["promoted"]))


def why(doc, ids, key) -> str:
    """The message line's sentence for a key pressed while its action doesn't apply."""
    a = next((x for x in ACTIONS if x["key"] == key), None)
    if a is None:
        return ""
    label = a["label"] if isinstance(a["label"], str) else key.removeprefix("sel:").capitalize()
    return a["needs"] or f"{label} doesn't apply to what is selected"


def entry(a: dict) -> dict:
    return {"value": a["key"], "label": a["label"], "hint": a["shortcut"], "group": a["group"]}


def bar_items(acts: list[dict]) -> list[dict]:
    """The context bar's buttons in rank order: [{key, label, shortcut, menu}]; `menu` lists a button's choices
    (Transpose ▾, Add effect ▾). Never the edit block. The bar shows up to five and folds the rest into ⋯."""
    items = []
    for a in (x for x in acts if x["importance"] == "primary" and x["group"] != "edit"):
        name = a["menu"] or a["label"]
        item = next((i for i in items if i["label"] == name), None)
        if item is None:
            item = {"key": "" if a["menu"] else a["key"], "label": name, "shortcut": "" if a["menu"] else a["shortcut"],
                    "menu": []}
            items.append(item)
        if a["menu"]:
            item["menu"].append(entry(a))
    return items


def folded(acts: list[dict]) -> list[dict]:
    """Menu entries, a long set of choices (Add effect: ten effects) folded into one "Add effect ▸" entry whose value
    is "menu:<name>" (the host opens its choices)."""
    sizes: dict[str, int] = {}
    for a in acts:
        sizes[a["menu"]] = sizes.get(a["menu"], 0) + 1
    out, seen = [], set()
    for a in acts:
        if a["menu"] and sizes[a["menu"]] > FOLD:
            if a["menu"] not in seen:
                seen.add(a["menu"])
                out.append({"value": f"menu:{a['menu']}", "label": f"{a['menu']} ▸", "hint": "", "group": a["group"]})
            continue
        out.append(entry(a))
    return out


def menu_entries(acts: list[dict]) -> list[dict]:
    """The right-click menu: every valid action in rank order, the edit block last (after a divider)."""
    return folded(acts)


def overflow(acts: list[dict], shown: int) -> list[dict]:
    """⋯: the bar's buttons past the first `shown`, then the secondary actions; never the edit block."""
    names = [i["label"] for i in bar_items(acts)[shown:]]
    rest = [a for a in acts if a["group"] != "edit" and
            (a["importance"] != "primary" or (a["menu"] or a["label"]) in names)]
    return folded(rest)


def submenu(acts: list[dict], value: str) -> list[dict]:
    return [entry(a) for a in acts if a["menu"] == value.removeprefix("menu:")]


def at_menu(doc, track_id: str, t: float, clipboard: bool) -> list[dict]:
    """Right-click on empty lane space (track_id) or on the ruler (""): what can be done at that time."""
    out = []
    if track_id and clipboard:
        out.append({"value": f"at:paste:{track_id}:{t}", "label": "Paste here", "hint": "Ctrl+V", "group": "here"})
    out.append({"value": f"at:marker:{t}", "label": "Add marker here", "hint": "M", "group": "here"})
    if track_id:
        out.append({"value": f"at:all:{track_id}", "label": "Select all on this track", "hint": "", "group": "select"})
    else:
        out.append({"value": f"at:section:{t}", "label": "Make a section from here", "hint": "", "group": "here"})
    return out
