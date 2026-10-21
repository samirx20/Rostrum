"""diff(a, b): the edits that turn tree a into tree b, by id (used by the script merge, outside changes,
restoring versions and gestures).

One pass over b in tree order: a new item is inserted (bare; its children follow one by one), an item that
changed list or fell out of order is moved, each right after its sibling in b. Then items gone from b are
removed (topmost only), then changed fields are set. Order inside a list is kept with a longest increasing
run, so one moved card is one Move, not a reshuffle.
"""
from __future__ import annotations

import bisect

from .edits import MISSING, Insert, Move, Remove, Set
from .tree import bare, child_keys, fields, index, walk


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
    if isinstance(a, dict) and isinstance(b, dict) and path:
        for k in list(a) + [k for k in b if k not in a]:
            _field_sets(id_, path + [k], a.get(k, MISSING), b.get(k, MISSING), out)
    elif not path:
        for k in list(a) + [k for k in b if k not in a]:
            _field_sets(id_, [k], a.get(k, MISSING), b.get(k, MISSING), out)
    elif a != b:
        out.append(Set(id_, path, b, a))


def diff(a: dict, b: dict, lists: dict) -> list:
    ia, ib = index(a, lists), index(b, lists)
    edits = []
    for parent in walk(b, lists):
        for key in child_keys(parent, lists):
            kids = parent.get(key, [])
            same = [(n, ia[c["id"]].index) for n, c in enumerate(kids)
                    if c["id"] in ia and (ia[c["id"]].parent, ia[c["id"]].key) == (parent["id"], key)]
            keep = {same[i][0] for i in _stable([p for _, p in same])}
            for n, child in enumerate(kids):
                after = kids[n - 1]["id"] if n else None
                if child["id"] not in ia:
                    edits.append(Insert(child["id"], parent["id"], key, n, bare(child, lists), after))
                elif n not in keep:
                    loc = ia[child["id"]]
                    edits.append(Move(child["id"], (loc.parent, loc.key, loc.index), (parent["id"], key, n), after))
    for id_, loc in ia.items():
        if id_ not in ib and loc.parent in ib:
            edits.append(Remove(id_, loc.parent, loc.key, loc.index, loc.item))
    for id_, loc in ia.items():
        if id_ in ib:
            _field_sets(id_, [], fields(loc.item, lists), fields(ib[id_].item, lists), edits)
    return edits
