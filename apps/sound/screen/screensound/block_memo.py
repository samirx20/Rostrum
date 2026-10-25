"""Each note's and hit's block made once: an edit makes again only the blocks of the items it changed (no Qt).

The document is never changed in place (rostrum_core.edits.fork): an item an edit did not touch is the very same
dict afterwards. So a block made from an item stays right for as long as that item is the same object and the
song's clock stays as it was: everything a block reads besides its own item (the tempo, meter, keys, markers …,
timeline.clock). `follow(clock)` empties the memo when the clock moved; a change that only adds, removes or reorders
tracks keeps every other track's blocks (adding a track to a 3-minute song made all ~1,600 again: ~75 ms). Before
the memo, every click on a 400-note song made all of the track's blocks twice (its row and the Editor's roll), and
the cost grew with the song.

A memo holds, per (track id, part), the blocks of the items it was last asked for, keyed by the item itself (kept,
so its id is never reused by another item while it is held); each call replaces that part's entries, so items gone
are dropped. A block handed out is shared: nobody may change it in place (a row's lanes are a new dict, `made`
with a key).
"""
from __future__ import annotations


class BlockMemo:
    def __init__(self):
        self._parts: dict = {}
        self._clock = None

    def clear(self):
        self._parts, self._clock = {}, None

    def follow(self, clock, tracks) -> bool:
        """Keep the blocks while the song's clock is the same (compared by value: an untouched part is the same
        object, so this is one pass over the song's top level), else empty the memo; parts of tracks no longer in
        `tracks` (ids) are dropped. True when the blocks were kept."""
        kept = self._clock is not None and clock == self._clock
        self._parts = {k: v for k, v in self._parts.items() if k[0] in tracks} if kept else {}
        self._clock = clock
        return kept

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


class Same:
    """A key equal only to the very same object (held, so its id is never reused): blocks that read more than their
    own item (a note held to the next one reads its track's notes) are kept only while that stays the same object."""
    __slots__ = ("x",)

    def __init__(self, x):
        self.x = x

    def __eq__(self, other):
        return isinstance(other, Same) and other.x is self.x

    __hash__ = None


def made(memo: BlockMemo | None, part, items, make, key=None) -> list[dict]:
    """The blocks of `items` (through the memo when there is one)."""
    return [make(x) for x in items] if memo is None else memo.made(part, items, make, key)
