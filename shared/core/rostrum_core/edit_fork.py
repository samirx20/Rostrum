"""Versions that share everything until edited (see edits.py: fork, copy on write) and the small helpers placing and
finding items in a version's lists."""
from __future__ import annotations

import copy

from .errors import RostrumError
from .edit_types import NO_AFTER
from .tree import Loc, index


def _missing(where, id_, choices):
    return RostrumError.not_found(where, "item", id_, choices)


def _place(lst: list, after, i: int, idx: dict) -> int:
    """Where an item goes in `lst`: after its sibling `after` when that is there (found through the index, checked by
    identity; a scan only when its kept position went stale: a redo of a 3,352-note Ctrl+D scanned for each, ~0.6 s),
    else at index `i`."""
    if after != NO_AFTER:
        if after is None:
            return 0
        loc = idx.get(after)
        if loc is not None and loc.index is not None and loc.index < len(lst) and lst[loc.index] is loc.item:
            return loc.index + 1
        pos = next((n for n, c in enumerate(lst) if c["id"] == after), None)
        if pos is not None:
            return pos + 1
    return max(0, min(i, len(lst)))


def _prev(lst: list, pos: int):
    return lst[pos - 1]["id"] if pos > 0 else None


class Fork(dict):
    """A version's index (id -> Loc) that also knows which items this version owns (may change in place). Owned
    items are kept here by object, so a dropped one's id() can never be taken for a shared item's."""

    def __init__(self, idx: dict):
        super().__init__(idx)
        self.owned: dict[int, dict] = {}
        self.owned_lists: dict[int, list] = {}       # child lists this version copied (by object, as `owned`)


def fork(data: dict, lists: dict, idx: dict | None = None) -> tuple[dict, Fork]:
    """(a new version of `data`, its index) sharing everything with `data` until edited. `idx`: data's index,
    when already known (its positions may be stale; edits look them up)."""
    f = Fork(idx if idx is not None else index(data, lists))
    return _own(f, data["id"], lists), f


def _own(idx: dict, id_: str, lists: dict) -> dict:
    """The item `id_` as this version's own copy (shallow), its parents first. Its child lists stay shared until an
    edit changes one (`_own_list`): an edit on a note copies the song, its track and the track's notes, and the song's
    other lists (markers, tempos, buses …) stay the very same objects, so a reader can tell by identity what changed."""
    loc = idx[id_]
    owned = getattr(idx, "owned", None)
    if owned is None or id(loc.item) in owned:
        return loc.item
    item = dict(loc.item)
    pos = None
    if loc.parent is not None:
        src = _own_list(idx, loc.parent, loc.key, lists)
        pos = _position(src, loc)
        src[pos] = item
    owned[id(item)] = item
    idx[id_] = Loc(item, loc.parent, loc.key, pos)
    return item


def _own_list(idx: dict, id_: str, key: str, lists: dict) -> list:
    """The child list `key` of item `id_` as this version's own (copied once per version; made when missing)."""
    item = _own(idx, id_, lists)
    lst = item.get(key)
    owned = getattr(idx, "owned_lists", None)
    if owned is None:
        return item.setdefault(key, [])
    if lst is None or id(lst) not in owned:
        lst = item[key] = list(lst or [])
        owned[id(lst)] = lst
    return lst


_PLAIN = frozenset({str, int, float, bool, type(None)})


def clone(v):
    """A deep copy of a document value (dicts, lists, plain values), several times faster than copy.deepcopy. A plain
    value inside is taken as it is, with no call for it (most of an item's fields: a whole-song Ctrl+D copied 3,607
    notes and hits in ~30,000 calls, ~35 ms)."""
    t = type(v)
    if t is dict:
        return {k: x if type(x) in _PLAIN else clone(x) for k, x in v.items()}
    if t is list:
        return [x if type(x) in _PLAIN else clone(x) for x in v]
    if t in _PLAIN:
        return v
    return copy.deepcopy(v)


def _own_many(idx, ids_, lists, where) -> list:
    """The items `ids_` as this version's own copies (as _own, one by one), each parent list owned once and each item
    found in it once: a whole-song Shift owns 3,607 notes and hits in ~4 ms instead of ~10 µs a note. One pass: owning a
    list owns its parent and that one's parents, never an item in it, so an item's place read before stays true."""
    owned = getattr(idx, "owned", None)
    if owned is None:
        return [_found(idx, i, where).item for i in ids_]
    out, lsts, where_is = [], {}, {}
    add, get, last, lst = out.append, idx.get, None, None   # last: the (parent, list) the item before sat in
    for id_ in ids_:
        loc = get(id_)
        if loc is None:
            raise _missing(where, id_, idx)
        item = loc.item
        if id(item) in owned:                       # owned already (an id twice, or a parent owned for its list)
            add(item)
            continue
        parent, key = loc.parent, loc.key
        if parent is None:
            add(_own(idx, id_, lists))
            continue
        if last is None or last[0] != parent or last[1] != key:
            last = parent, key
            lst = lsts.get(last)
            if lst is None:
                lst = lsts[last] = _own_list(idx, parent, key, lists)
        pos = loc.index
        if pos is None or pos >= len(lst) or lst[pos] is not item:
            if last not in where_is:                # stale positions: look the list up once, not once per item
                where_is[last] = {id(c): i for i, c in enumerate(lst)}
            pos = where_is[last][id(item)]
        new = lst[pos] = dict(item)
        owned[id(new)] = new
        idx[id_] = Loc(new, parent, key, pos)
        add(new)
    return out


def _found(idx, id_, where):
    loc = idx.get(id_)
    if loc is None:
        raise _missing(where, id_, idx)
    return loc


def _position(lst: list, loc: Loc) -> int:
    """Where the item sits now: a kept index's positions go stale when siblings come and go, so check, then look."""
    if loc.index is not None and loc.index < len(lst) and lst[loc.index] is loc.item:
        return loc.index
    return next(n for n, c in enumerate(lst) if c is loc.item)
