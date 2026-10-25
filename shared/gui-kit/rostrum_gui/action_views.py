"""The action list's views (actions.py): pure dicts the kit's QML draws from the resolved entries of
`ActionList.available`. The context bar (primaries; actions sharing a `bar` name are one button with a menu), the
right-click menu (valid actions primary first, then the edit block last; a long set of choices folds into one
"Name" entry with a side menu) and Ctrl+K's "Do" commands. They only arrange: what is valid was settled by the list's one guard.
"""
from __future__ import annotations

FOLD = 2            # a set of more choices than this is one entry with a side menu (right-click and ⋯): 2D, H29


def asked(e) -> str:
    """Its name in a menu or Ctrl+K: an action with amounts ends in "…" (picking it opens the amounts popover)."""
    return e["label"] + ("…" if e.get("amounts") and not e["label"].endswith("…") else "")


def _short(e):
    """One choice in a bar button's menu or under ⋯ (the menus' shape)."""
    return {"value": e["id"], "label": asked(e), "keys": e["keys"], "group": e["group"]}


def off_rows(entries: list[dict]) -> list[dict]:
    """Without the actions that live on a settings row (Action.row): the bar, panel and right-click never repeat them."""
    return [e for e in entries if not e.get("row")]


def row_buttons(entries: list[dict]) -> dict:
    """{param id: {label, id, menu}} for the actions that sit on a settings row (Action.row). One action is a plain button
    (its id); several on one row are one button with a menu, titled by their `bar` name."""
    by_row: dict[str, list[dict]] = {}
    for e in entries:
        if e.get("row"):
            by_row.setdefault(e["row"], []).append(e)
    out = {}
    for row, es in by_row.items():
        if len(es) == 1 and not es[0]["bar"]:
            out[row] = {"label": es[0].get("row_label") or es[0]["label"], "id": es[0]["id"], "menu": []}
        else:
            out[row] = {"label": es[0]["bar"] or "Choose", "id": "", "menu": [_short(e) for e in es]}
    return out


def bar(entries: list[dict], what: str) -> dict:
    """The context bar: every primary in order (QML folds the lowest into ⋯ by width); actions sharing `bar` are
    one button with a menu. `more`: the secondary ones, for ⋯. The edit block is never here."""
    entries = off_rows(entries)
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
        row = {"value": e["id"], "label": asked(e), "keys": e["keys"], "group": e["group"], "sub": []}
        if e["bar"] and sizes[e["bar"]] > FOLD:
            if e["bar"] not in folded:
                folded[e["bar"]] = {"value": "menu:" + e["bar"], "label": e["bar"], "keys": "", "group": e["group"],
                                    "sub": []}
                out.append(folded[e["bar"]])
            folded[e["bar"]]["sub"].append(row)
        else:
            out.append(row)
    return out


def menu(entries: list[dict], short: tuple | None = None) -> list[dict]:
    """Right-click. With `short` (actions.SHORT_MENU): only those jobs, in its order and blocks, everywhere the same.
    Without: the valid actions, primary first, then the edit block as the last group."""
    entries = off_rows(entries)
    if short:
        order = {job: (b, n) for b, (_, jobs) in enumerate(short) for n, job in enumerate(jobs)}
        block = {job: name for name, jobs in short for job in jobs}
        mine = sorted((e for e in entries if e["job"] in order), key=lambda e: order[e["job"]])
        return [{"value": e["id"], "label": asked(e), "keys": e["keys"], "group": block[e["job"]], "sub": []} for e in mine]
    plain = sorted((e for e in entries if not e["edit"]), key=lambda e: e["importance"] != "primary")
    return _fold(plain) + [{"value": e["id"], "label": asked(e), "keys": e["keys"], "group": "edit", "sub": []}
                           for e in entries if e["edit"]]


def commands(entries: list[dict], what: str) -> list[dict]:
    """Ctrl+K's "Do" group, in the command box's shape (commands.py) plus the key."""
    out = []
    for e in entries:
        c = {"key": e["id"], "label": asked(e), "hint": what, "keys": e["keys"],
             "words": e["bar"], "lead": e["bar"], "weight": 0 if e["importance"] == "primary" else 1}
        out.append({**c, "calls": e["calls"]} if not e["do"] else {**c, "do": e["do"]})
    return out


KEEP = ("group", "ungroup")     # in the short menu AND first in the panel: the most used way to make a selection one


def _cols(labels: list[str]) -> int:
    """Buttons a line in the panel's wide row: as many as fit the longest name (up to four)."""
    n, longest = len(labels), max(len(t) for t in labels)
    return min(n, 4 if longest <= 10 else 3 if longest <= 13 else 2)


def _in_row(label: str, title: str) -> str:
    """A name inside its titled row, without the title said again: "Align left" under Align is "Left"."""
    for sep in (": ", " "):
        if title and label.lower().startswith(title.lower() + sep):
            rest = label[len(title) + len(sep):]
            return rest[:1].upper() + rest[1:]
    return label


SUB = " › "         # a bar name "Chord › Make a chord": the Chord ▾ button, its "Make a chord" entry a side menu


def _bar_menu(items: list[dict]) -> list[dict]:
    """A titled row's button menu: its actions in order, a divider where `group` changes, the ones sharing a side-menu
    name (the bar name after " › ") one entry whose `sub` holds them (shown where the first of them ranks)."""
    out, subs = [], {}
    for i in items:
        row = {"value": i["id"], "label": i["label"], "keys": i["keys"],
               "group": i["group"], "sub": []}
        if not i["sub"]:
            out.append(row)
        elif i["sub"] in subs:
            subs[i["sub"]]["sub"].append(row)
        else:
            subs[i["sub"]] = {"value": "menu:" + i["sub"], "label": i["sub"], "keys": "", "group": i["group"], "sub": [row]}
            out.append(subs[i["sub"]])
    return out


def panel(entries: list[dict], short: tuple | None = None) -> dict:
    """The settings panel's actions, first (SPEC 2d-design-v2 §8.3): every valid action but the short menu's and the
    ones marked `panel: False`. The primary ones are buttons, in order; actions sharing a `bar` are one titled row
    ("Combine": Union, Subtract …), the others one untitled row where its first one ranks.
    Fixed slots (F11): what applies to ONE item comes first, then what needs two or more, each by rank; so selecting
    one more item only adds actions after the ones already there (Align keeps its place on a text, two shapes or a
    mix). The secondary ones are one "⋯" menu at the very end of the row (folded like right-click); with no main
    action at all there is no row (a lone "⋯" is never shown: those actions stay on right-click and in Ctrl+K).
    {rows: [{title, cols, items: [{id, label, keys}]}], more: [...]}"""
    menu_jobs = {j for _, jobs in (short or ()) for j in jobs} - set(KEEP)
    mine = [e for e in off_rows(entries) if not e["edit"] and e["job"] not in menu_jobs and e.get("panel", True)]
    rows, by = [], {}
    for e in (e for e in mine if e["importance"] == "primary"):
        title, _, sub = e["bar"].partition(SUB)
        if title not in by:
            by[title] = {"title": title, "items": []}
            rows.append(by[title])
            by[title]["slot"] = (min(e.get("min_targets", 1), 2), e["rank"])
        by[title]["items"].append({"id": e["id"], "label": _in_row(e["label"], sub or title), "keys": e["keys"],
                                  "icon": e.get("icon", ""), "full": e["label"], "group": e["group"], "sub": sub,
                                  "amounts": bool(e.get("amounts")) and not e.get("asks")})   # its ▾ (asks: the button opens)
    for r in rows:
        r["cols"] = _cols([i["label"] for i in r["items"]])
        r["menu"] = _bar_menu(r["items"])
    rows.sort(key=lambda r: r.pop("slot"))     # fixed slots: one-item actions first, then by rank (stable sort)
    return {"rows": rows, "more": _fold([e for e in mine if e["importance"] != "primary"]) if rows else []}
