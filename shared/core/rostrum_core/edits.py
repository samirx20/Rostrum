"""The four edits (OPERATIONS.md § 3), each addressed by id, each carrying what was there before so it can be
reversed without an old copy of the document.

`apply(data, lists, edit)` changes `data` in place and returns the edit as it really happened (actual
before-values and positions), which is what history stores. Positions use `after` (the sibling it follows)
when given, so an edit still lands right when other people inserted things meanwhile.

`fork(data)` starts a new version of a document without copying it: edits through the fork's index copy only
the items they change and the items above them (copy on write); everything else, values included, is shared
with the old version, which therefore must never be changed in place.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field

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


def to_dict(e) -> dict:
    d = {"edit": next(k for k, c in KINDS.items() if isinstance(e, c)), **asdict(e)}
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in d.items()}


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


def fork(data: dict, lists: dict, idx: dict | None = None) -> tuple[dict, Fork]:
    """(a new version of `data`, its index) sharing everything with `data` until edited. `idx`: data's index,
    when already known (its positions may be stale; edits look them up)."""
    f = Fork(idx if idx is not None else index(data, lists))
    return _own(f, data["id"], lists), f


def _own(idx: dict, id_: str, lists: dict) -> dict:
    """The item `id_` as this version's own copy (shallow, child lists copied), its parents first."""
    loc = idx[id_]
    owned = getattr(idx, "owned", None)
    if owned is None or id(loc.item) in owned:
        return loc.item
    item = dict(loc.item)
    for key in child_keys(item, lists):
        if key in item:
            item[key] = list(item[key])
    pos = None
    if loc.parent is not None:
        src = _own(idx, loc.parent, lists)[loc.key]
        pos = _position(src, loc)
        src[pos] = item
    owned[id(item)] = item
    idx[id_] = Loc(item, loc.parent, loc.key, pos)
    return item


def _set(item, lists, e, where):
    if not e.path or e.path[0] == "id" or e.path[0] in child_keys(item, lists):
        raise RostrumError(codes.INTERNAL, where, f"{e.id}.{e.path}", "is not a field a Set may change")
    node = item
    for k in e.path[:-1]:                           # nested values may be shared with other versions: copy the way
        if isinstance(node.get(k), dict):
            node[k] = dict(node[k])
        node = node.setdefault(k, {})
    last = e.path[-1]
    before = copy.deepcopy(node.get(last, MISSING))
    if e.value == MISSING:
        node.pop(last, None)
    else:
        node[last] = copy.deepcopy(e.value)
    return Set(e.id, list(e.path), copy.deepcopy(e.value), before)


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
        if any(i in idx for i in subtree_ids(e.item, lists)):
            raise RostrumError(codes.CONFLICT, where, f'"{e.id}"', "is already in this document")
        lst = _own(idx, e.parent, lists).setdefault(e.key, [])
        pos = _place(lst, e.after, e.index)
        lst.insert(pos, copy.deepcopy(e.item))
        _add(idx, lst[pos], e.parent, e.key, pos, lists)
        return Insert(e.id, e.parent, e.key, pos, copy.deepcopy(e.item), _prev(lst, pos))
    loc = idx[e.id]
    if loc.parent is None:
        raise RostrumError(codes.BAD_ARGUMENT, where, '"root"', "can't be removed or moved")
    src = _own(idx, loc.parent, lists)[loc.key]
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
        dst = _own(idx, parent, lists).setdefault(key, [])
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
    sub = index(item, lists)
    sub[item["id"]] = Loc(item, parent, key, pos)
    idx.update(sub)
    if getattr(idx, "owned", None) is not None:     # a fresh copy: this version's own
        idx.owned.update((id(loc.item), loc.item) for loc in sub.values())


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
