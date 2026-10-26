"""What a subtree holds, remembered per item object: a document is never changed in place (rostrum_core.edits.fork),
so an item a change didn't reach is the very same object afterwards, and its answer is still right. A drag's step
makes new objects only on the path from the root to the moved layer: asking the whole composition again ("an
expression anywhere?", "a marker time anywhere?") then looks at that path, not at every layer and key (200 layers:
~1-2 ms of each move per question, on the screen's thread).

    timed = Subtree(lambda item: {"timed"} if item.get("marker") else (), lambda item: item.get("layers", ()))
    "timed" in timed(comp)
"""
from __future__ import annotations

EMPTY = frozenset()


class Subtree:
    """`own(item)` -> what the item itself holds (an iterable of facts); `children(item)` -> the items inside it. Called
    with an item: the facts of it and everything inside it, as a frozenset."""

    MOST = 50_000                # remembered items (one dict entry each); past it the memory starts again

    def __init__(self, own, children):
        self._own, self._children, self._kept = own, children, {}

    def __call__(self, item: dict) -> frozenset:
        hit = self._kept.get(id(item))
        if hit is not None and hit[0] is item:          # (held, so its id is still its own)
            return hit[1]
        facts = frozenset(self._own(item))
        for child in self._children(item):
            inside = self(child)
            if inside:
                facts = facts | inside
        if len(self._kept) >= self.MOST:
            self._kept.clear()
        self._kept[id(item)] = (item, facts or EMPTY)
        return facts or EMPTY
