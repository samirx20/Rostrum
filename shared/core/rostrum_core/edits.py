"""The four edits (OPERATIONS.md § 3), each addressed by id, each carrying what was there before so it can be
reversed without an old copy of the document.

`apply(data, lists, edit)` changes `data` in place and returns the edit as it really happened (actual
before-values and positions), which is what history stores. Positions use `after` (the sibling it follows)
when given, so an edit still lands right when other people inserted things meanwhile.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field

from .errors import RostrumError, codes
from .tree import child_keys, index, subtree_ids

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


def _set(item, lists, e, where):
    if not e.path or e.path[0] == "id" or e.path[0] in child_keys(item, lists):
        raise RostrumError(codes.INTERNAL, where, f"{e.id}.{e.path}", "is not a field a Set may change")
    node = item
    for k in e.path[:-1]:
        node = node.setdefault(k, {})
    last = e.path[-1]
    before = copy.deepcopy(node.get(last, MISSING))
    if e.value == MISSING:
        node.pop(last, None)
    else:
        node[last] = copy.deepcopy(e.value)
    return Set(e.id, list(e.path), copy.deepcopy(e.value), before)


def apply(data: dict, lists: dict, e, where: str = "edit"):
    idx = index(data, lists)
    target = e.parent if isinstance(e, Insert) else e.id
    if target not in idx:
        raise _missing(where, target, idx)
    if isinstance(e, Set):
        return _set(idx[e.id].item, lists, e, where)
    if isinstance(e, Insert):
        if set(subtree_ids(e.item, lists)) & set(idx):
            raise RostrumError(codes.CONFLICT, where, f'"{e.id}"', "is already in this document")
        lst = idx[e.parent].item.setdefault(e.key, [])
        pos = _place(lst, e.after, e.index)
        lst.insert(pos, copy.deepcopy(e.item))
        return Insert(e.id, e.parent, e.key, pos, copy.deepcopy(e.item), _prev(lst, pos))
    loc = idx[e.id]
    if loc.parent is None:
        raise RostrumError(codes.BAD_ARGUMENT, where, '"root"', "can't be removed or moved")
    src = idx[loc.parent].item[loc.key]
    prev = _prev(src, loc.index)
    if isinstance(e, Remove):
        item = src.pop(loc.index)
        return Remove(e.id, loc.parent, loc.key, loc.index, item, prev)
    if isinstance(e, Move):
        parent, key, i = e.to
        if parent not in idx:
            raise _missing(where, parent, idx)
        if parent in subtree_ids(loc.item, lists):
            raise RostrumError(codes.CHECK_FAILED, where, f'"{e.id}"', f"can't move into its own child {parent!r}")
        item = src.pop(loc.index)
        dst = idx[parent].item.setdefault(key, [])
        pos = _place(dst, e.after, i)
        dst.insert(pos, item)
        return Move(e.id, (loc.parent, loc.key, loc.index), (parent, key, pos), _prev(dst, pos), prev)
    raise TypeError(f"not an edit: {e!r}")


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
