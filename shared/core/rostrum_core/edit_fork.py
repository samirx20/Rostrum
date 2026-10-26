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


_PLAIN = (str, int, float, bool, type(None))


def clone(v):
    """A deep copy of a document value (dicts, lists, plain values), several times faster than copy.deepcopy."""
    t = type(v)
    if t in _PLAIN:
        return v
    if t is dict:
        return {k: clone(x) for k, x in v.items()}
    if t is list:
        return [clone(x) for x in v]
    return copy.deepcopy(v)


def _own_many(idx, ids_, lists, where) -> list:
    """The items `ids_` as this version's own copies (as _own, one by one), each parent list owned once and each item
    found in it once: a whole-song Shift owns 3,352 notes in a few ms instead of ~10 µs a note."""
    owned = getattr(idx, "owned", None)
    out, todo = [], {}
    for id_ in ids_:
        loc = idx.get(id_)
        if loc is None:
            raise _missing(where, id_, idx)
        if owned is None or id(loc.item) in owned:
            out.append(loc.item)
        elif loc.parent is None:
            out.append(_own(idx, id_, lists))
        else:
            out.append(None)
            todo.setdefault((loc.parent, loc.key), []).append((len(out) - 1, id_))
    for (parent, key), group in todo.items():
        lst, where_is = _own_list(idx, parent, key, lists), None
        for n, id_ in group:
            loc = idx[id_]                          # again: owning a list may have owned it (an id twice, a parent)
            if id(loc.item) in owned:
                out[n] = loc.item
                continue
            pos = loc.index
            if pos is None or pos >= len(lst) or lst[pos] is not loc.item:
                if where_is is None:                # stale positions: look the list up once, not once per item
                    where_is = {id(c): i for i, c in enumerate(lst)}
                pos = where_is[id(loc.item)]
            item = lst[pos] = out[n] = dict(loc.item)
            owned[id(item)] = item
            idx[id_] = Loc(item, parent, key, pos)
    return out


def _position(lst: list, loc: Loc) -> int:
    """Where the item sits now: a kept index's positions go stale when siblings come and go, so check, then look."""
    if loc.index is not None and loc.index < len(lst) and lst[loc.index] is loc.item:
        return loc.index
    return next(n for n, c in enumerate(lst) if c is loc.item)
