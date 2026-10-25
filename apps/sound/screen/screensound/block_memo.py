"""Each note's and hit's block made once: an edit makes again only the blocks of the items it changed (no Qt).

The document is never changed in place (rostrum_core.edits.fork): an item an edit did not touch is the very same
dict afterwards. So a block made from an item stays right for as long as that item is the same object and the
song's clock stays as it was: everything a block reads besides its own item (the tempo, meter, keys, markers …,
timeline.clock). `follow(clock)` empties the memo when the clock moved; a change that only adds, removes or reorders
tracks keeps every other track's blocks (adding a track to a 3-minute song made all ~1,600 again: ~75 ms). Before
the memo, every click on a 400-note song made all of the track's blocks twice (its row and the Editor's roll), and
the cost grew with the song.

A memo holds, per (track id, part), the items it was last asked for and their blocks (the items kept, so an id is
never reused by another item while it is held). An edit forks only the lists it changed, and in them only the items
it touched: the items before and after those are the very same objects in the same order. So a call compares the
new list with the last one from both ends by identity (in C, `operator.is_`) and makes or looks up only the items in
between: an edit's cost is the items it changed, not the track's length (each item looked up by id grew with the
song: ~2.5 ms a click on a 3-minute drum track). A block handed out is shared: nobody may change it in place (a
row's lanes are a new dict, `made` with a key).
"""
from __future__ import annotations

from collections import Counter
from itertools import islice
from operator import is_


def same_ends(new: list, old: list) -> tuple[int, int]:
    """(a, b): the first `a` and the last `b` entries of `new` and `old` are the very same objects (a + b never
    more than the shorter list)."""
    short = min(len(new), len(old))
    head = list(map(is_, new, old))
    a = head.index(False) if False in head else short
    tail = list(islice(map(is_, reversed(new), reversed(old)), short - a))
    b = tail.index(False) if False in tail else len(tail)
    return a, b


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
        held = self._parts.get(part)
        if held is None or not held[2] == key:
            out = [make(x) for x in items]
        elif held[0] is items:
            return held[1]
        else:
            was, blocks = held[0], held[1]
            a, b = same_ends(items, was)
            old = {id(x): bl for x, bl in zip(was[a:len(was) - b], blocks[a:len(blocks) - b])}
            mid = [old.get(id(x)) or make(x) for x in items[a:len(items) - b]]
            out = blocks[:a] + mid + blocks[len(blocks) - b:]
        self._parts[part] = (items, out, key)
        return out

    def tally(self, part, items, key_of) -> Counter:
        """How many of `items` have each `key_of(item)` (a drum track's drums), counted again only for the items
        the edit changed (the lists' same ends are the same items)."""
        held = self._parts.get(part)
        if held is not None and held[0] is items:
            return held[1]
        if held is None:
            c = Counter(map(key_of, items))
        else:
            a, b = same_ends(items, held[0])
            c = held[1].copy()
            c.subtract(map(key_of, held[0][a:len(held[0]) - b]))
            c.update(map(key_of, items[a:len(items) - b]))
            c = +c                                      # (a key no item has any more is gone)
        self._parts[part] = (items, c)
        return c

    def last_end(self, part, blocks) -> float:
        """Where the last of `blocks` ends (0 for none), worked out again only from the blocks the edit changed
        (all of them only when one that ended last went or moved)."""
        held = self._parts.get(part)
        if held is not None and held[0] is blocks:
            return held[1]
        end = lambda x: x["t"] + x["dur"]                   # noqa: E731
        if held is not None:
            a, b = same_ends(blocks, held[0])
            if all(end(x) < held[1] for x in held[0][a:len(held[0]) - b]):
                e = max([held[1], *map(end, blocks[a:len(blocks) - b])])
                self._parts[part] = (blocks, e)
                return e
        e = max(map(end, blocks), default=0.0)
        self._parts[part] = (blocks, e)
        return e


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
