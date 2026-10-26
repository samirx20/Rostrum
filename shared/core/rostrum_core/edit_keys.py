"""What an edit touches, and when two sets of touched keys collide (see edits.py)."""
from __future__ import annotations

from .tree import child_keys, subtree_ids
from .edit_types import Insert, Move, Remove, Set, Shift


def keys(e, lists: dict) -> set[tuple]:
    """What an edit touches, for collisions: (id, *path) for a field, (id,) for a whole item."""
    if isinstance(e, Set):
        return {(e.id, *e.path)}
    if isinstance(e, (Insert, Remove)):
        if not child_keys(e.item, lists):           # a note or a key: itself (a walk per item cost a whole-song Esc ~10 ms)
            return {(e.id,)}
        return {(i,) for i in subtree_ids(e.item, lists)} or {(e.id,)}
    if isinstance(e, Move):
        return {(e.id, "@place")}
    if isinstance(e, Shift):
        return {(i, *e.path) for i in e.ids}
    raise TypeError(f"not an edit: {e!r}")


def heads(k: tuple):
    """Every leading part of key k, itself included: ("n1",), ("n1", "at"), ("n1", "at", "beat")."""
    return (k[:n] for n in range(1, len(k) + 1))


def overlap(a: set[tuple], b: set[tuple]) -> set[tuple]:
    """Keys in a that collide with b: equal, or one inside the other (an item and one of its fields). Looked up through
    b's leading parts, never pair by pair (two whole-song steps were 11 million compares: a redo took 6.8 s)."""
    if not a or not b:
        return set()
    inside = {h for y in b for h in heads(y)}
    return {x for x in a if x in inside or any(h in b for h in heads(x))}


def key_text(k: tuple) -> str:
    return ".".join(str(p) for p in k if p != "@place") + (" (place)" if "@place" in k else "")
