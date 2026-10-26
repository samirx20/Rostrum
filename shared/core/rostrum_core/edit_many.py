"""A `Many` edit applied (see edits.py): N items brought into, or taken out of, their lists as one edit.

The result is exactly what applying its Inserts (or Removes) one by one in order would give, and each is recorded as
that one-by-one apply records it (its `after`: the sibling it followed), so `reverse` is the per-item reverse in
reverse order. But each list is rebuilt once: one by one, every insert after the first found its sibling's kept place
stale and looked through the list again (a whole-song Ctrl+D: 3,607 items into ~1,000-long lists). Lists are taken
in an order that keeps a parent there for the items going into it (and an item there until the items inside it went).
"""
from __future__ import annotations

from .errors import RostrumError, codes
from .tree import Loc, child_keys, index, subtree_ids
from .edit_types import NO_AFTER, Insert, Many, Remove
from .edit_fork import Fork, _missing, _own_list, clone


def apply_many(idx: dict, lists: dict, e: Many, where: str) -> Many:
    edits = e.edits
    if not edits:
        return Many([])
    kind = type(edits[0])
    if kind not in (Insert, Remove) or any(type(x) is not kind for x in edits):
        raise RostrumError(codes.INTERNAL, where, "a Many edit", "holds only Inserts or only Removes")
    return Many(_inserts(idx, lists, edits, where) if kind is Insert else _removes(idx, lists, edits, where))


def _groups(entries, key) -> dict:
    out: dict = {}
    for n, x in enumerate(entries):
        out.setdefault(key(x), []).append(n)
    return out


def _inserts(idx, lists, edits, where) -> list:
    new = set()
    for x in edits:
        for i in (subtree_ids(x.item, lists) if child_keys(x.item, lists) else (x.item["id"],)):
            if i in idx or i in new:
                raise RostrumError(codes.CONFLICT, where, f'"{i}"', "is already in this document")
            new.add(i)
    done: list = [None] * len(edits)
    pending = _groups(edits, lambda x: (x.parent, x.key))
    while pending:                                  # a list goes in once its parent is there (it may come in here)
        ready = [g for g in pending if g[0] in idx]
        if not ready:
            raise _missing(where, next(iter(pending))[0], idx)
        for g in ready:
            _insert_list(idx, lists, g, [(n, edits[n]) for n in pending.pop(g)], done)
    return done


def _insert_list(idx, lists, g, entries, done):
    """One list: every entry placed where one-by-one Inserts would put it, then the list rebuilt once."""
    parent, key = g
    lst = _own_list(idx, parent, key, lists)
    base, follow = list(lst), {}                    # follow: sibling id (None: the start) -> items put right after it
    ids = {c["id"] for c in base}
    tail, count = (base[-1]["id"] if base else None), len(base)
    placed = []                                     # (entry number, item, the sibling it follows)
    for n, x in entries:
        a = x.after
        if a == NO_AFTER or (a is not None and a not in ids):
            i = x.index                             # by index (as edit_fork._place: a sibling not found is skipped)
            if i >= count:
                a = tail
            elif i <= 0:
                a = None
            else:                                   # inside the list as it now stands: rare, so made only then
                base = _built(base, follow)
                follow = {}
                a = base[i - 1]["id"]
        item = clone(x.item)
        follow.setdefault(a, []).append(item)
        ids.add(item["id"])
        if a == tail:
            tail = item["id"]
        count += 1
        placed.append((n, item, a))
    lst[:] = _built(base, follow)
    _reindex(idx, lists, lst, parent, key)
    at = {id(c): p for p, c in enumerate(lst)} if len(placed) > 8 else None
    for n, item, a in placed:
        pos = at[id(item)] if at is not None else next(p for p, c in enumerate(lst) if c is item)
        kept = item if isinstance(idx, Fork) else clone(item)
        done[n] = Insert(item["id"], parent, key, pos, kept, a)


def _built(base: list, follow: dict) -> list:
    """`base` with the items `follow` puts after each sibling: the last one put after a sibling sits right after it
    (one by one, each insert goes right after its sibling, before the ones put there earlier), each followed by the
    items put after it."""
    if not follow:
        return base
    out, stack = [], []
    add, more, pop = out.append, stack.extend, stack.pop

    def drain(a):
        fl = follow.get(a)
        if fl:
            more(fl)
        while stack:
            c = pop()
            add(c)
            fl = follow.get(c["id"])
            if fl:
                more(fl)
    drain(None)
    for c in base:
        add(c)
        drain(c["id"])
    return out


def _reindex(idx, lists, lst, parent, key):
    """Every item of the rebuilt list at its new place (an item brought in: its own items too)."""
    for p, c in enumerate(lst):
        loc = idx.get(c["id"])
        if loc is None:
            if child_keys(c, lists):
                idx.update(index(c, lists))
            idx[c["id"]] = Loc(c, parent, key, p)
        elif loc.index != p or loc.item is not c:
            idx[c["id"]] = Loc(c, parent, key, p)


def _removes(idx, lists, edits, where) -> list:
    gone = {}
    for n, x in enumerate(edits):
        loc = idx.get(x.id)
        if loc is None or x.id in gone:
            raise _missing(where, x.id, idx)
        if loc.parent is None:
            raise RostrumError(codes.BAD_ARGUMENT, where, '"root"', "can't be removed or moved")
        gone[x.id] = n
    done: list = [None] * len(edits)
    pending = _groups(edits, lambda x: (idx[x.id].parent, idx[x.id].key))
    while pending:                                  # a list goes out before an item holding it goes (if one does)
        g = next((g for g in pending if not any(i in gone and _list_of(idx, i) == g for h in pending if h != g
                                                for i in _above(idx, h[0]))), None)
        if g is None:
            raise RostrumError(codes.INTERNAL, where, "a Many edit", "can't order its lists")
        _remove_list(idx, lists, g, pending.pop(g), edits, done)
    return done


def _above(idx, id_):
    """id_ and every item above it."""
    while id_ is not None:
        yield id_
        loc = idx.get(id_)
        id_ = loc.parent if loc is not None else None


def _list_of(idx, i):
    loc = idx.get(i)
    return (loc.parent, loc.key) if loc is not None else None


def _remove_list(idx, lists, g, ns, edits, done):
    """One list: the items taken out in one pass. Each records the sibling it followed when one-by-one removes reach it
    (the nearest one before it still there then: kept, or taken out later) and its place before the edit."""
    parent, key = g
    lst = _own_list(idx, parent, key, lists)
    rank = {edits[n].id: n for n in ns}
    keep, stack, prev = [], [], {}                  # stack: (rank, id) of the items before, nearest last
    inf = len(edits)
    for p, c in enumerate(lst):
        r = rank.get(c["id"], inf)
        while stack and stack[-1][0] <= r:
            stack.pop()
        if r != inf:
            prev[c["id"]] = (stack[-1][1] if stack else None, p, c)
        else:
            keep.append(c)
        stack.append((r, c["id"]))
    for n in ns:
        id_ = edits[n].id
        a, p, item = prev[id_]
        for i in subtree_ids(item, lists):
            del idx[i]
        done[n] = Remove(id_, parent, key, p, item, a)
    lst[:] = keep
    _reindex(idx, lists, lst, parent, key)
