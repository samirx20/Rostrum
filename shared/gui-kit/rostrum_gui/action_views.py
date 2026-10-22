"""The action list's views (actions.py): pure dicts the kit's QML draws from the resolved entries of
`ActionList.available`. The context bar (primaries; actions sharing a `bar` name are one button with a menu), the
right-click menu (valid actions primary first, then the edit block last; a long set of choices folds into one
"Name" entry with a side menu) and Ctrl+K's "Do" commands. They only arrange: what is valid was settled by the list's one guard.
"""
from __future__ import annotations

FOLD = 4            # a bar button with more choices than this is one entry with a side menu (right-click and ⋯)


def _short(e):
    """One choice in a bar button's menu or under ⋯ (the menus' shape)."""
    return {"value": e["id"], "label": e["label"], "keys": e["keys"], "group": e["group"]}


def bar(entries: list[dict], what: str) -> dict:
    """The context bar: every primary in order (QML folds the lowest into ⋯ by width); actions sharing `bar` are
    one button with a menu. `more`: the secondary ones, for ⋯. The edit block is never here."""
    items, by_name = [], {}
    for e in entries:
        if e["edit"] or e["importance"] != "primary":
            continue
        if not e["bar"]:
            items.append({"id": e["id"], "label": e["label"], "keys": e["keys"], "menu": []})
        elif e["bar"] in by_name:
            by_name[e["bar"]]["menu"].append(_short(e))
        else:
            by_name[e["bar"]] = {"id": "bar:" + e["bar"], "label": e["bar"], "keys": "", "menu": [_short(e)]}
            items.append(by_name[e["bar"]])
    more = _fold([e for e in entries if not e["edit"] and e["importance"] != "primary"])
    return {"what": what, "items": items, "more": more}


def _fold(entries: list[dict]) -> list[dict]:
    """Menu rows in order; a bar set with more than FOLD choices is one entry whose `sub` holds them (the kit's
    ActionMenu draws the side arrow, so the label stays plain)."""
    sizes: dict[str, int] = {}
    for e in entries:
        sizes[e["bar"]] = sizes.get(e["bar"], 0) + 1
    out, folded = [], {}
    for e in entries:
        row = {"value": e["id"], "label": e["label"], "keys": e["keys"], "group": e["group"], "sub": []}
        if e["bar"] and sizes[e["bar"]] > FOLD:
            if e["bar"] not in folded:
                folded[e["bar"]] = {"value": "menu:" + e["bar"], "label": e["bar"], "keys": "", "group": e["group"],
                                    "sub": []}
                out.append(folded[e["bar"]])
            folded[e["bar"]]["sub"].append(row)
        else:
            out.append(row)
    return out


def menu(entries: list[dict]) -> list[dict]:
    """Right-click: the valid actions, primary first, then the edit block as the last group."""
    plain = sorted((e for e in entries if not e["edit"]), key=lambda e: e["importance"] != "primary")
    return _fold(plain) + [{"value": e["id"], "label": e["label"], "keys": e["keys"], "group": "edit", "sub": []}
                           for e in entries if e["edit"]]


def commands(entries: list[dict], what: str) -> list[dict]:
    """Ctrl+K's "Do" group, in the command box's shape (commands.py) plus the key."""
    out = []
    for e in entries:
        c = {"key": e["id"], "label": e["label"], "hint": what, "keys": e["keys"],
             "words": e["bar"], "weight": 0 if e["importance"] == "primary" else 1}
        out.append({**c, "calls": e["calls"]} if not e["do"] else {**c, "do": e["do"]})
    return out
