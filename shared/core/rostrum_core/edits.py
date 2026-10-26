"""The edits (OPERATIONS.md § 3), each addressed by id, each carrying what was there before so it can be
reversed without an old copy of the document. Four are per item; `Shift` is one edit for a uniform change of many
items (a whole-song nudge: ids + one amount), so it costs one history entry, not one per item; `Many` is many Inserts
or many Removes as one edit (a whole-song Ctrl+D or Delete), each list rebuilt once (edit_many.py).

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

This module is the one door: the pieces live in edit_types, edit_fork, edit_apply and edit_keys.
"""
from __future__ import annotations

from .edit_types import (KINDS, MISSING, NO_AFTER, Insert, Many, Move, Remove, Set, Shift, flat, from_dict, ids,
                         reverse, to_dict)
from .edit_fork import Fork, clone, fork
from .edit_apply import apply
from .edit_keys import heads, key_text, keys, overlap

__all__ = ["KINDS", "MISSING", "NO_AFTER", "Insert", "Many", "Move", "Remove", "Set", "Shift", "flat", "from_dict", "ids", "reverse",
           "to_dict", "Fork", "clone", "fork", "apply", "heads", "key_text", "keys", "overlap"]
