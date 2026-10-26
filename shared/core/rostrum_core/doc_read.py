"""A document's reading side: its index of items, lookups, who changed what, and the door it changes through
(see document.py)."""
from __future__ import annotations

import contextlib

from .diff import _at
from .errors import RostrumError
from .history import Change
from .tree import index
from .who import Who


class ReadMixin:
    # reading
    def _index(self) -> dict:
        """id -> Loc for the current data, kept until the data is replaced (every change makes a new tree; a tree is
        never written in place, edits.fork). One `is` per read (screens ask 100+ times per change). The one exception
        is a set-up filling a new document's data before its first change (tests do: `doc.data["tracks"].append`):
        until the history has a step, its top lists are compared too. Positions may be stale (parent_of looks)."""
        if self._idx[0] is not self.data or (not self.history.changes and self._idx[1] != self._top()):
            self._idx = (self.data, self._top(), index(self.data, self.kind.lists))
        return self._idx[2]

    def locs(self) -> dict:
        """id -> Loc for the current data (items and parents are current; positions may be stale, see parent_of)."""
        return self._index()

    def _indexed(self, data, idx):
        self._idx = (data, self._top(data), idx)

    def _top(self, data=None):
        data = self.data if data is None else data
        return tuple((id(data.get(k)), len(data.get(k) or ())) for k in self.kind.lists.get(data.get("type"), []))

    def item(self, id_) -> dict:
        idx = self._index()
        if id_ not in idx:
            raise RostrumError.not_found("document", "item", id_, idx)
        return idx[id_].item

    def has(self, id_) -> bool:
        return id_ in self._index()

    def items(self):
        return (loc.item for loc in list(self._index().values()))

    def parent_of(self, id_):
        idx = self._index()
        loc = idx.get(id_)
        if loc is None:
            raise RostrumError.not_found("document", "item", id_, idx)
        return loc.parent, loc.key, (_at(idx, id_) if loc.parent is not None else loc.index)

    @property
    def seq(self) -> int:
        return self.history.seq

    def who_changed(self, id_, field_=None) -> Change | None:
        return self.history.who_changed(id_, field_)

    # the door
    def _door(self):
        return self.live.door() if self.live is not None else contextlib.nullcontext([])

    def locked_by(self, id_) -> Who | None:
        """Who set item `id_`'s lock last (the lock rule and its plain refusal); None when nobody did through an op."""
        c = self.history.who_changed(id_, "locked")
        return c.who if c is not None else None
