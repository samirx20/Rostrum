"""Several items selected: the settings they all share, as one list of rows (no Qt).

- Same kind: all its params. Mixed kinds: the params every kind's field operation has, by name and type (in the
  first item's order, with the first item's labels and groups).
- A row's state is the AND of each item's: a param shows only while it applies to every selected item. A value that
  differs is `mixed` (the widget says "Mixed"; number, text, choice, colour, toggle). What can't be shown "mixed" —
  an expression or binding, a pick, a list, a curve, a file — is absent when the items differ.
- The key mark: "onkey" / "keyed" when every item is; else "still" when any could be animated ("" when one can't).
Each item's own rows come from rows.evaluate (and rows.omit) as for one item; `merge` folds them together.
- An item's name (ONE_ONLY) is absent: several items never share one typed name.
- Mixed kinds also get a narrowing line per kind ("3 layers", "1 text": click one to keep only that kind, `by_kind`),
  and the panel's last line says who changed the selection last and when (`last_change`, `ago`).
"""
from __future__ import annotations

from types import SimpleNamespace

from rostrum_core import edits as E

from .rows import _headers

SAME_ONLY = ("list",)                       # types shown only when every item has the same value
ONE_ONLY = ("name",)                        # an item's own name: never typed for several at once (both would be called it)
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


def merge(each: list[list[dict]], differs=frozenset()) -> list[dict]:
    """One row list from each item's evaluated rows (all from one static layout; rows an item lacks are dropped).
    `differs`: ids of rows whose value differs among more items than `each` holds (an app that folds alike items
    into one, Sound's many_rows): those rows are `mixed` as if every item had been passed."""
    others = [{r["id"]: r for r in rows} for rows in each[1:]]
    out = []
    for r in each[0]:
        alike = [o.get(r["id"]) for o in others]
        if any(a is None for a in alike) or r["id"] in ONE_ONLY:
            continue
        out.append(_param(r, alike, r["id"] in differs) if r["row"] == "param" else {**r, "mixed": False})
    holds = {r["id"]: r["holds"] for r in out if r["row"] == "param"}
    for r in out:
        if r["row"] != "param":
            r["holds"] = any(holds.get(m, False) for m in r["members"])
            if "open" in r:
                r["open"] = next((x["open"] for x in [r] + [o[r["id"]] for o in others] if x["open"] is not None), None)
    return _headers(out)


def _param(r: dict, alike: list[dict], differs: bool = False) -> dict:
    rows = [r] + alike                       # this item first, then the others' same row
    mixed = differs or any(a["value"] != r["value"] for a in alike)
    same_only = r["type"] in SAME_ONLY or r.get("control") in SAME_ONLY_CONTROLS
    exprs_differ = any(a["expr"] != r["expr"] for a in alike)
    ok = all(a["holds"] for a in rows) and not exprs_differ and not (mixed and (same_only or r["expr"]))
    anims = [a["anim"] for a in rows]
    anim = ("" if "" in anims else anims[0] if len(set(anims)) == 1 else
            "keyed" if all(a in ("keyed", "onkey") for a in anims) else "still")
    return {**r, "holds": ok, "valid": ok and all(a["valid"] for a in rows), "mixed": mixed, "anim": anim}


def by_kind(kinds: list[tuple[str, str]]) -> list[dict]:
    """The narrowing lines for a selection: `kinds` = [(type, kind in words)] per selected item. One line per kind, in
    the order they first appear, {"kind", "label": "3 layers", "count"}; none when every item is one kind."""
    order = dict.fromkeys(t for t, _ in kinds)
    if len(order) < 2:
        return []
    words = dict(kinds)
    n = {t: sum(1 for k, _ in kinds if k == t) for t in order}
    return [{"kind": t, "count": n[t], "label": f"{n[t]} {words[t].lower()}{'s' if n[t] > 1 else ''}"} for t in order]


def last_change(doc, ids):
    """The newest change still in force that touched any of these items (an Insert, Set, Move or Remove of one), or
    None: the panel's "Last changed by" line. An undo or redo step isn't one; the step it acted on is.
    Asked on every pick and after every change: first the newest steps in force (after a whole-song Right on the
    selection it is the very first: asking each of 3,607 items for its own last step cost ~7 ms of every whole-song
    edit), then each item's own steps (`_by_item`), not the whole history back to the item's last change."""
    h, best = doc.history, None
    by_item, by_step, seen = _by_item(h), _indexed[id(h)][3], 0
    for c in reversed(h.changes):
        if c.original and h.done[c.seq]:
            if not by_step.get(c.seq, frozenset()).isdisjoint(ids):
                return c
            seen += 1
            if seen == NEWEST:
                break
    for i in dict.fromkeys(ids):
        c = next((c for c in reversed(by_item.get(i, ())) if h.done[c.seq]), None)
        if c is not None and (best is None or c.seq > best.seq):
            best = c
    return best


NEWEST = 4                  # the newest steps in force looked at first (last_change)
_indexed: dict = {}         # id(history) -> [history, steps read, {item id: its original steps, oldest first},
                            #                 {step: the items it touched}]


def _by_item(h) -> dict:
    """The original steps that touched each item, read once: a history only grows (Undo is a step of its own)."""
    got = _indexed.get(id(h))
    if got is None or got[0] is not h or got[1] > len(h.changes):
        if len(_indexed) > 8:
            _indexed.clear()
        got = _indexed[id(h)] = [h, 0, {}, {}]
    index = got[2]
    for c in h.changes[got[1]:]:
        if c.original:
            touched = dict.fromkeys(i for e in c.edits for i in E.ids(e) if i is not None)
            got[3][c.seq] = frozenset(touched)
            for i in touched:
                index.setdefault(i, []).append(c)
    got[1] = len(h.changes)
    return index


def ago(t: float, now: float) -> str:
    """How long ago, in plain words: "just now", "2 min ago", "3 h ago", "4 d ago"."""
    s = max(0, now - t)
    return ("just now" if s < 60 else f"{int(s // 60)} min ago" if s < 3600
            else f"{int(s // 3600)} h ago" if s < 86400 else f"{int(s // 86400)} d ago")
