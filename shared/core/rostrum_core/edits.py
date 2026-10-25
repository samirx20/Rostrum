"""The four edits (OPERATIONS.md § 3), each addressed by id, each carrying what was there before so it can be
reversed without an old copy of the document.

`apply(data, lists, edit)` changes `data` in place and returns the edit as it really happened (actual
before-values and positions), which is what history stores. Positions use `after` (the sibling it follows)
when given, so an edit still lands right when other people inserted things meanwhile.

`fork(data)` starts a new version of a document without copying it: edits through the fork's index copy only
the items they change and the items above them (copy on write); everything else, values included, is shared
with the old version, which therefore must never be changed in place.

An edit through a fork copies what it brings in once (`clone`): the tree and the edit history stores share that
copy. Neither is ever written in place afterwards: an item an Insert brought in is not the fork's own, so a later
edit in the same call copies it first, like any shared item. Edits on a plain index (opening a file, a script's
merge) write the tree in place, so there an inserted item's record is a copy of its own.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields

from .errors import RostrumError, codes
from .tree import Loc, child_keys, index, subtree_ids

MISSING = "<missing>"     # a Set whose value is MISSING removes the field; before=MISSING: it wasn't there
NO_AFTER = "<index>"      # place by index, not after a sibling


@dataclass
class Set:
    id: str
    path: list
    value: object = MISSING
    before: object = MISSING


@dataclass
class Insert:
    id: str
    parent: str
    key: str
    index: int
    item: dict = field(default_factory=dict)
    after: object = NO_AFTER          # sibling id, None = first, NO_AFTER = use index


@dataclass
class Remove:
    id: str
    parent: str = ""
    key: str = ""
    index: int = 0
    item: dict = field(default_factory=dict)
    after: object = NO_AFTER          # filled on apply: the sibling it followed (for the reverse)


@dataclass
class Move:
    id: str
    from_: tuple = ()                 # (parent, key, index)
    to: tuple = ()
    after: object = NO_AFTER
    from_after: object = NO_AFTER     # filled on apply


KINDS = {"set": Set, "insert": Insert, "remove": Remove, "move": Move}


_NAMES = {c: k for k, c in KINDS.items()}
_FIELDS = {c: [f.name for f in fields(c)] for c in KINDS.values()}


def to_dict(e) -> dict:
    """The edit as its history line holds it. Its values are shared, not copied (dataclasses.asdict deep-copied every
    item a big Ctrl+D brought in, only to write it out): the caller writes it and drops it."""
    out = {"edit": _NAMES[type(e)]}
    for name in _FIELDS[type(e)]:
        v = getattr(e, name)
        out[name] = list(v) if isinstance(v, tuple) else v
    return out


def from_dict(d) -> object:
    d = dict(d)
    cls = KINDS[d.pop("edit")]
    if cls is Move:
        d["from_"], d["to"] = tuple(d["from_"]), tuple(d["to"])
    return cls(**d)


def _missing(where, id_, choices):
    return RostrumError.not_found(where, "item", id_, choices)


def _place(lst: list, after, idx: int) -> int:
    if after != NO_AFTER:
        if after is None:
            return 0
        pos = next((i for i, c in enumerate(lst) if c["id"] == after), None)
        if pos is not None:
            return pos + 1
    return max(0, min(idx, len(lst)))


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


def _set(item, lists, e, where):
    if not e.path or e.path[0] == "id" or e.path[0] in child_keys(item, lists):
        raise RostrumError(codes.INTERNAL, where, f"{e.id}.{e.path}", "is not a field a Set may change")
    node = item
    for k in e.path[:-1]:                           # nested values may be shared with other versions: copy the way
        if isinstance(node.get(k), dict):
            node[k] = dict(node[k])
        node = node.setdefault(k, {})
    last = e.path[-1]
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
        pos = _place(lst, e.after, e.index)
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
        pos = _place(dst, e.after, i)
        dst.insert(pos, item)
        idx[e.id] = Loc(item, parent, key, pos)
        return Move(e.id, (loc.parent, loc.key, at), (parent, key, pos), _prev(dst, pos), prev)
    raise TypeError(f"not an edit: {e!r}")


def _position(lst: list, loc: Loc) -> int:
    """Where the item sits now: a kept index's positions go stale when siblings come and go, so check, then look."""
    if loc.index is not None and loc.index < len(lst) and lst[loc.index] is loc.item:
        return loc.index
    return next(n for n, c in enumerate(lst) if c is loc.item)


def _add(idx: dict, item: dict, parent: str, key: str, pos: int, lists: dict):
    if child_keys(item, lists):
        idx.update(index(item, lists))
    idx[item["id"]] = Loc(item, parent, key, pos)


def reverse(e):
    """The edit that undoes an applied edit."""
    if isinstance(e, Set):
        return Set(e.id, list(e.path), e.before, e.value)
    if isinstance(e, Insert):
        return Remove(e.id, e.parent, e.key, e.index, e.item)
    if isinstance(e, Remove):
        return Insert(e.id, e.parent, e.key, e.index, e.item, e.after)
    if isinstance(e, Move):
        return Move(e.id, e.to, e.from_, e.from_after)
    raise TypeError(f"not an edit: {e!r}")


def keys(e, lists: dict) -> set[tuple]:
    """What an edit touches, for collisions: (id, *path) for a field, (id,) for a whole item."""
    if isinstance(e, Set):
        return {(e.id, *e.path)}
    if isinstance(e, (Insert, Remove)):
        return {(i,) for i in subtree_ids(e.item, lists)} or {(e.id,)}
    if isinstance(e, Move):
        return {(e.id, "@place")}
    raise TypeError(f"not an edit: {e!r}")


def overlap(a: set[tuple], b: set[tuple]) -> set[tuple]:
    """Keys in a that collide with b: equal, or one inside the other (an item and one of its fields)."""
    return {x for x in a for y in b if x[:len(y)] == y or y[:len(x)] == x}


def key_text(k: tuple) -> str:
    return ".".join(str(p) for p in k if p != "@place") + (" (place)" if "@place" in k else "")
