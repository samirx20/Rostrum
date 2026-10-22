"""Locked items (`locked` field: a 2D layer, a Sound track): no operation may change a locked item or anything inside
it, for anyone (a person, an agent, a script), until it is unlocked. The one lock check for every app: run.plan calls
`check` after each operation with the edits it made, so whatever an operation reaches (its targets, a clip moved
onto a locked track, a section op touching every track) is caught. Setting `locked` on the item itself always passes,
so locking and unlocking work. The refusal is one plain sentence naming the item and who locked it.
"""
from __future__ import annotations

from . import edits as E
from .errors import RostrumError, codes
from .tree import walk


def _holder(idx, id_):
    """The item itself or the nearest parent that is locked, else None."""
    while id_ is not None and id_ in idx:
        if idx[id_].item.get("locked"):
            return idx[id_].item
        id_ = idx[id_].parent
    return None


def _held(e, idx, lists):
    """(the locked item that holds this edit's change, the item changed), or (None, None)."""
    if isinstance(e, E.Set):
        if e.path and e.path[0] == "locked":            # locking / unlocking the item itself: ask its parents only
            return _holder(idx, idx[e.id].parent if e.id in idx else None), e.id
        return _holder(idx, e.id), e.id
    if isinstance(e, E.Remove):
        inner = next((i for i in walk(e.item, lists) if i.get("locked")), None)
        return (inner, e.id) if inner is not None else (_holder(idx, e.parent), e.id)
    if isinstance(e, E.Insert):
        return _holder(idx, e.parent), e.id
    places = [e.id] + [p[0] for p in (e.from_, e.to) if p]
    return next(((h, e.id) for p in places if (h := _holder(idx, p)) is not None), (None, None))


def check(edits, idx, lists, where, locked_by=None) -> None:
    """Refuse (raise) when any of these edits changes a locked item or something inside one."""
    for e in edits:
        held, changed = _held(e, idx, lists)
        if held is None:
            continue
        by = locked_by(held["id"]) if locked_by else None
        whose = f'"{held.get("name") or held["id"]}" ({held["id"]})'
        it = idx[changed].item if changed in idx else getattr(e, "item", None) or {"id": changed}
        subject, problem = ((whose, "is locked") if held["id"] == changed else
                            (f'"{it.get("name") or changed}" ({changed})', f"is inside {whose}, which is locked"))
        raise RostrumError(codes.CHECK_FAILED, where, subject, problem + (f" by {by}" if by else ""),
                           hint="Unlock it first, then try again.")
