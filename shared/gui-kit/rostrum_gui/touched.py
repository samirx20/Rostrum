"""What a document change touched, so each screen part redoes only its own work (an edit's whole cost on the screen's
thread stays under one frame on a busy scene).

Every change carries its edits; their keys say which items and fields it touched (rostrum_core.edits.keys). The
bridge keeps the last change's `Touched` (`bridge.touched()`); a part asks `reaches(ids)` before it rebuilds, and
does nothing for a change elsewhere. A drag's step is told the same way, from the edits of that step alone (on top of
the step before). When the kit can't tell (a reset, another program's steps taken in), `touched()` is None:
everything counts as touched. A change that adds, removes or moves items, or renames one, reaches every part: lists
of names and pick lists name other items.
"""
from __future__ import annotations

from rostrum_core import edits as E

NAMES = frozenset({"name"})          # a field other items' rows and lists show (a pick naming another item)


class Touched:
    def __init__(self, keys: set[tuple], structural: bool):
        self.keys, self.structural = keys, structural
        self.ids = {k[0] for k in keys}
        self.fields = {(k[0], k[1]) for k in keys if len(k) > 1}

    def reaches(self, doc, ids) -> bool:
        """Did the change touch any of `ids`, an item above one (a parent's time or place moves it) or one inside
        one (a group's rows read its members)? Always True for an add, remove, move or rename anywhere."""
        if self.structural or not ids:
            return self.structural
        idx = doc._index()
        near = set()
        for i in ids:
            loc = idx.get(i)
            while loc is not None:
                near.add(loc.item["id"])
                loc = idx.get(loc.parent) if loc.parent else None
        if near & self.ids:
            return True
        return any(idx.get(t) is not None and _inside(idx, t, set(ids)) for t in self.ids)


def _inside(idx, item_id, ids: set) -> bool:
    loc = idx.get(item_id)
    while loc is not None and loc.parent:
        if loc.parent in ids:
            return True
        loc = idx.get(loc.parent)
    return False


def of(doc, event) -> Touched | None:
    """What the change or the drag's step touched, or None when it can't be told (a reset that doesn't say, a change
    with no edits listed). A drag's step carries its own edits (on top of the step before), a drag taken back (Esc)
    the edits that undid it: the one "what did this preview change" every part reads."""
    c = getattr(event, "change", None)
    edits = c.edits if event.kind == "change" and c is not None else getattr(event, "edits", None)
    if event.kind != "change" and edits == []:
        return Touched(set(), False)                # a step that changed nothing reaches nothing
    if not edits:
        return None
    lists = doc.kind.lists
    keys = set().union(*(E.keys(e, lists) for e in edits))
    structural = any(not isinstance(e, E.Set) for e in edits) or any(len(k) > 1 and k[1] in NAMES for k in keys)
    return Touched(keys, structural)
