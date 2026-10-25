"""What a document change touched, so each screen part redoes only its own work (an edit's whole cost on the screen's
thread stays under one frame on a busy scene).

Every change carries its edits; their keys say which items and fields it touched (rostrum_core.edits.keys). The
bridge keeps the last change's `Touched` (`bridge.touched()`); a part asks `reaches(ids)` before it rebuilds, and
does nothing for a change elsewhere. A drag's step is told the same way, from the edits of that step alone (on top of
the step before). When the kit can't tell (a reset, another program's steps taken in), `touched()` is None:
everything counts as touched. A change that adds, removes or moves items, or renames one, reaches every part: lists
of names and pick lists name other items.

A drag's step says more: which fields of an item it moved (`fields_of`), so the settings panel works out only those
rows; steps a part let pass between two of its runs add up (`joined`).
"""
from __future__ import annotations

from rostrum_core import edits as E

NAMES = frozenset({"name"})          # a field other items' rows and lists show (a pick naming another item)


class Touched:
    def __init__(self, keys: set[tuple], structural: bool):
        self.keys, self.structural = keys, structural
        self.ids = {k[0] for k in keys}
        self.fields = {(k[0], k[1]) for k in keys if len(k) > 1}
        self._above: set | None = None       # every item above a touched one (`reaches`: once per change)

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
        if self._above is None:              # (a whole-song Right: 3,352 notes walked up once, not per question)
            self._above = set()
            for t in self.ids:
                loc = idx.get(t)
                while loc is not None and loc.parent and loc.parent not in self._above:
                    self._above.add(loc.parent)
                    loc = idx.get(loc.parent)
        return not self._above.isdisjoint(ids)

    def fields_of(self, doc, item_id) -> set[str] | None:
        """The item's own fields this touched: a field of it, and for a key in it the field the key animates (the one
        animation model, rostrum_core.keys: an owner's `keys`, each naming its `prop`). None when it can't be told that
        narrowly: an add, remove, move or rename; the item touched whole; an item above it (its time or place moves
        every value it shows); anything else inside it."""
        if self.structural:
            return None
        idx, out = doc._index(), {f for i, f in self.fields if i == item_id}
        for i in self.ids:
            loc = idx.get(i)
            if i == item_id:
                if not out:
                    return None                     # touched whole, no field named
            elif loc is not None and loc.parent == item_id and loc.key == "keys" and "prop" in loc.item:
                out.add(loc.item["prop"])
            elif loc is None or _inside(idx, i, {item_id}) or _inside(idx, item_id, {i}):
                return None
        return out

    def joined(self, other: "Touched | None") -> "Touched | None":
        """This and `other` together (two steps a part takes in at once); None (can't tell) stays None."""
        return None if other is None else Touched(self.keys | other.keys, self.structural or other.structural)


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
    structural = any(not isinstance(e, (E.Set, E.Shift)) for e in edits) or any(len(k) > 1 and k[1] in NAMES for k in keys)
    return Touched(keys, structural)
