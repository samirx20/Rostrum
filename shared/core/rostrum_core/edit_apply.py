"""Applying one edit to a document's tree, in place or through a fork (see edits.py)."""
from __future__ import annotations

from math import copysign

from .errors import RostrumError, codes
from .tree import Loc, child_keys, index, subtree_ids
from .edit_types import MISSING, Insert, Many, Move, Remove, Set, Shift
from .edit_many import apply_many
from .edit_fork import (Fork, _missing, _own, _own_list, _own_many, _place, _position, _prev, clone)


def _field(item, lists, id_, path, where):
    """The dict holding `path`'s last key in `item` (nested values copied on the way: they may be shared)."""
    if not path or path[0] == "id" or path[0] in child_keys(item, lists):
        raise RostrumError(codes.INTERNAL, where, f"{id_}.{path}", "is not a field an edit may change")
    node = item
    for k in path[:-1]:                             # nested values may be shared with other versions: copy the way
        if isinstance(node.get(k), dict):
            node[k] = dict(node[k])
        node = node.setdefault(k, {})
    return node


def _set(item, lists, e, where):
    node, last = _field(item, lists, e.id, e.path, where), e.path[-1]
    before = node.get(last, MISSING)                # the old version's value: never written in place, so kept as is
    value = clone(e.value)
    if value == MISSING:
        node.pop(last, None)
    else:
        node[last] = value
    return Set(e.id, list(e.path), value, before)


def apply(data: dict, lists: dict, e, where: str = "edit", idx: dict | None = None):
    """`idx`: the document's index (tree.index), used and kept up to date, so a run of edits (opening a file's
    history, a script's merge, one call's plan) indexes the tree once instead of once per edit."""
    if idx is None:
        idx = index(data, lists)
    if isinstance(e, Shift):
        return _shift(idx, lists, e, where)
    if isinstance(e, Many):
        return apply_many(idx, lists, e, where)
    target = e.parent if isinstance(e, Insert) else e.id
    if target not in idx:
        raise _missing(where, target, idx)
    if isinstance(e, Set):
        done = _set(_own(idx, e.id, lists), lists, e, where)
        if e.path[0] == "type":                     # its kind (so its child lists) may have changed
            idx.clear()
            idx.update(index(data, lists))
        return done
    if isinstance(e, Insert):
        if any(i in idx for i in (subtree_ids(e.item, lists) if child_keys(e.item, lists) else (e.item["id"],))):
            raise RostrumError(codes.CONFLICT, where, f'"{e.id}"', "is already in this document")
        lst = _own_list(idx, e.parent, e.key, lists)
        pos = _place(lst, e.after, e.index, idx)
        item = clone(e.item)                        # through a fork: one copy, the tree's and the history's (see top)
        lst.insert(pos, item)
        _add(idx, item, e.parent, e.key, pos, lists)
        kept = item if isinstance(idx, Fork) else clone(item)
        return Insert(e.id, e.parent, e.key, pos, kept, _prev(lst, pos))
    loc = idx[e.id]
    if loc.parent is None:
        raise RostrumError(codes.BAD_ARGUMENT, where, '"root"', "can't be removed or moved")
    src = _own_list(idx, loc.parent, loc.key, lists)
    at = _position(src, loc)
    prev = _prev(src, at)
    if isinstance(e, Remove):
        item = src.pop(at)
        for i in subtree_ids(item, lists):
            del idx[i]
        return Remove(e.id, loc.parent, loc.key, at, item, prev)
    if isinstance(e, Move):
        parent, key, i = e.to
        if parent not in idx:
            raise _missing(where, parent, idx)
        if parent in subtree_ids(loc.item, lists):
            raise RostrumError(codes.CHECK_FAILED, where, f'"{e.id}"', f"can't move into its own child {parent!r}")
        item = src.pop(at)
        dst = _own_list(idx, parent, key, lists)
        pos = _place(dst, e.after, i, idx)
        dst.insert(pos, item)
        idx[e.id] = Loc(item, parent, key, pos)
        return Move(e.id, (loc.parent, loc.key, at), (parent, key, pos), _prev(dst, pos), prev)
    raise TypeError(f"not an edit: {e!r}")


def _shift(idx, lists, e, where):
    """A Shift applied: every item owned once (_own_many), each number moved, and the old values its reverse would not
    give back exactly kept in `back`. A sum already on the rounding grid (a multiple of 2**-places: 12.25 + 0.25 at
    4 places has at most 4 decimals) is what round() would give, so round() is asked only off the grid (a whole-song
    nudge and its undo: 7,214 round() calls, ~3 ms, became none)."""
    path, last, by, places, to, back = list(e.path), e.path[-1], e.by, e.places, e.to or None, {}
    if path[0] in ("type", "locked"):
        raise RostrumError(codes.INTERNAL, where, f"{path}", "is not a field a Shift may change")
    items, head, bad, rnd = _own_many(idx, e.ids, lists, where), path[:-1], {}, round
    fixed = places is not None
    grid = 2.0 ** places if fixed and type(places) is int and places >= 0 else None
    for id_, item in zip(e.ids, items):
        kind = item.get("type")
        no = bad.get(kind)
        if no is None:                              # the field rule (_field) asked once per kind, not per item
            no = bad[kind] = path[0] == "id" or path[0] in child_keys(item, lists)
        if no:
            raise RostrumError(codes.INTERNAL, where, f"{id_}.{path}", "is not a field an edit may change")
        node = item
        for k in head:                              # nested values may be shared with other versions: copy the way
            v = node.get(k)
            if type(v) is dict:
                v = node[k] = dict(v)
            node = v if v is not None else node.setdefault(k, {})
        before = node.get(last, MISSING)
        t = type(before)
        if t is not float and t is not int:
            raise RostrumError(codes.INTERNAL, where, f"{id_}.{path}", f"is {before!r}, not a number a Shift can move")
        if to is not None and id_ in to:
            value = to[id_]
        else:
            value = before + by
            if fixed and (grid is None or not (value * grid).is_integer()):
                value = rnd(value, places)
        node[last] = value
        undone = value - by
        if fixed and (grid is None or not (undone * grid).is_integer()):
            undone = rnd(undone, places)
        if undone != before or type(undone) is not t or (not undone and copysign(1, undone) != copysign(1, before)):
            back[id_] = before                      # (0.0 + 1/3 - 1/3 at 4 places is -0.0: equal, not the same)
    return Shift(list(e.ids), path, by, places, dict(e.to), back)


def _add(idx: dict, item: dict, parent: str, key: str, pos: int, lists: dict):
    if child_keys(item, lists):
        idx.update(index(item, lists))
    idx[item["id"]] = Loc(item, parent, key, pos)
