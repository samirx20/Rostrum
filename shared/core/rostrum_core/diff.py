"""diff(a, b): the edits that turn tree a into tree b, by id (used by the script merge, outside changes,
restoring versions and gestures).

One pass over b in tree order: a new item is inserted (bare; its children follow one by one), an item that
changed list or fell out of order is moved, each right after its sibling in b. Then items gone from b are
removed (topmost only), then changed fields are set. Order inside a list is kept with a longest increasing
run, so one moved card is one Move, not a reshuffle.

Versions made by edits.fork share every unchanged item and value, so a shared item (`is`) is skipped whole:
one stroke changed among 10,000 costs a walk of the changed branch, not a comparison of every value.
"""
from __future__ import annotations

import bisect
import json

from .edits import MISSING, Insert, Move, Remove, Set
from .tree import bare, child_keys, fields, index


def _stable(positions: list[int]) -> set[int]:
    """Indexes (into positions) of a longest increasing run; those items keep their place."""
    tails, tail_at, prev = [], [], [None] * len(positions)
    for i, p in enumerate(positions):
        j = bisect.bisect_left(tails, p)
        if j == len(tails):
            tails.append(p)
            tail_at.append(i)
        else:
            tails[j], tail_at[j] = p, i
        prev[i] = tail_at[j - 1] if j else None
    out, i = set(), (tail_at[-1] if tail_at else None)
    while i is not None:
        out.add(i)
        i = prev[i]
    return out


def _field_sets(id_, path, a, b, out):
    if a is b:
        return
    if isinstance(a, dict) and isinstance(b, dict) and path:
        for k in list(a) + [k for k in b if k not in a]:
            _field_sets(id_, path + [k], a.get(k, MISSING), b.get(k, MISSING), out)
    elif not path:
        for k in list(a) + [k for k in b if k not in a]:
            _field_sets(id_, [k], a.get(k, MISSING), b.get(k, MISSING), out)
    elif a != b or (repr(a) != repr(b) and _written(a) != _written(b)):   # 0 and 0.0 are equal in Python but not in
        # the file (its hash); repr tells them apart at C speed, the file's own text only decides when repr differs
        out.append(Set(id_, path, b, a))


def _written(v) -> str:
    """A value as the file writes it, so a change the file sees is never skipped as "no change"."""
    return "" if v is MISSING else json.dumps(v, sort_keys=True)


def _at(idx: dict, id_: str) -> int:
    """Where item id_ sits in its list now (a kept index's positions may be stale)."""
    loc = idx[id_]
    lst = idx[loc.parent].item[loc.key]
    if loc.index is not None and loc.index < len(lst) and lst[loc.index] is loc.item:
        return loc.index
    return next(n for n, c in enumerate(lst) if c is loc.item)


def _changed_walk(b: dict, ia: dict, lists: dict):
    """b's items in tree order, without the insides of items shared with a (nothing in there changed)."""
    stack = [b]
    while stack:
        item = stack.pop()
        yield item
        for key in reversed(child_keys(item, lists)):
            stack.extend(c for c in reversed(item.get(key, []))
                         if not (c["id"] in ia and ia[c["id"]].item is c))


def diff(a: dict, b: dict, lists: dict, ia: dict | None = None, ib: dict | None = None) -> list:
    """`ia`, `ib`: a's and b's indexes when already known (positions may be stale)."""
    ia = ia if ia is not None else index(a, lists)
    ib = ib if ib is not None else index(b, lists)
    edits = []
    for parent in (_changed_walk(b, ia, lists) if a is not b else ()):
        was = ia[parent["id"]].item if parent["id"] in ia else {}
        for key in child_keys(parent, lists):
            kids = parent.get(key, [])
            old = was.get(key, []) if key in child_keys(was, lists) else []
            if kids is old:
                continue
            at = {c["id"]: n for n, c in enumerate(old)}
            same = [(n, at[c["id"]]) for n, c in enumerate(kids) if c["id"] in at]
            keep = {same[i][0] for i in _stable([p for _, p in same])}
            for n, child in enumerate(kids):
                after = kids[n - 1]["id"] if n else None
                if child["id"] not in ia:
                    edits.append(Insert(child["id"], parent["id"], key, n, bare(child, lists), after))
                elif n not in keep:
                    loc = ia[child["id"]]
                    edits.append(Move(child["id"], (loc.parent, loc.key, _at(ia, child["id"])), (parent["id"], key, n),
                                      after))
    for id_, loc in ia.items():
        if id_ not in ib and loc.parent in ib:
            edits.append(Remove(id_, loc.parent, loc.key, _at(ia, id_), loc.item))
    for id_, loc in ia.items():
        if id_ in ib and ib[id_].item is not loc.item:
            _field_sets(id_, [], fields(loc.item, lists), fields(ib[id_].item, lists), edits)
    return edits
