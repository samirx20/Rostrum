"""Each note's and hit's block made once: an edit makes again only the blocks of the items it changed (no Qt).

The document is never changed in place (rostrum_core.edits.fork): an item an edit did not touch is the very same
dict afterwards. So a block made from an item stays right for as long as that item is the same object and the
song's times and keys stay as they were. Those move only in a change the rows view makes everything again for
(RowsView._rebuild), which clears the memo. Before it, every click on a 400-note song made all of the track's blocks
twice (its row and the Editor's roll), and the cost grew with the song.

A memo holds, per (track id, part), the blocks of the items it was last asked for, keyed by the item itself (kept,
so its id is never reused by another item while it is held); each call replaces that part's entries, so items gone
are dropped. A block handed out is shared: nobody may change it in place (a row's lanes are a new dict, `made`
with a key).
"""
from __future__ import annotations


class BlockMemo:
    def __init__(self):
        self._parts: dict = {}

    def clear(self):
        self._parts = {}

    def made(self, part, items, make, key=None) -> list[dict]:
        """`make(item)` for each item, except those of the last call for `part` that are the same object (and `key`)."""
        old, new, out = self._parts.get(part, {}), {}, []
        for x in items:
            hit = old.get(id(x))
            b = hit[2] if hit is not None and hit[0] is x and hit[1] == key else make(x)
            new[id(x)] = (x, key, b)
            out.append(b)
        self._parts[part] = new
        return out


def made(memo: BlockMemo | None, part, items, make, key=None) -> list[dict]:
    """The blocks of `items` (through the memo when there is one)."""
    return [make(x) for x in items] if memo is None else memo.made(part, items, make, key)
