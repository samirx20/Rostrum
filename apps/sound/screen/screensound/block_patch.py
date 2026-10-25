"""A row's or the roll's blocks sent to the screen as differences: the ids gone and the blocks new or changed.

Each read of a QML list copies all of it, so sending a drum row's 300 hits again for one hit added cost a few ms per
list and grew with the song (3,000 blocks: ~27 ms, M4). A small change goes as a patch (`diff`), which the screen
applies to the list it shows (qml/Blocks.js, the same rule as `apply` here); a big one (most blocks moved, another
track) goes whole. The arrangement's row model keeps the last whole list sent for each row (`held`): a patched row
leaves the model's value as it was, and when a whole list follows, a row the screen had patched is told to drop its
patch (`resets`), so the screen shows the model's value again even when that value did not change.

A whole list goes as JSON text (`text`), which the screen parses once (Blocks.js `parse`): handing Qt a list of
dicts converted every block field by field (3,352 notes: ~150-250 ms of a whole-song Right or Esc), the text costs a
few ms each way. Made once per list (the same list object is the same text).
"""
from __future__ import annotations

import json

from .block_memo import same_ends

MAX = 64            # changed blocks a patch may carry; more, and the whole list goes


def diff(old: list | None, new: list) -> tuple[list, list] | None:
    """(ids gone, blocks new or changed) taking `old` to `new`; None when it is cheaper to send `new` whole. A block
    the edit did not touch is the very same object in both (block_memo.py): only what lies between the lists' same
    ends is compared, so a patch costs what changed, not the track's length."""
    if old is None:
        return None
    a, b = same_ends(new, old)
    was = {x["id"]: x for x in old[a:len(old) - b]}
    mid = new[a:len(new) - b]
    ids = {x["id"] for x in mid}
    gone = [i for i in was if i not in ids]
    put = [x for x in mid if was.get(x["id"]) != x]
    n = len(gone) + len(put)
    return (gone, put) if n <= MAX and n < max(len(new), 1) else None


def apply(blocks: list, gone: list, put: list) -> list:
    """What the screen does with a patch (Blocks.js): changed blocks in their place, new ones at the end."""
    drop, by = set(gone), {b["id"]: b for b in put}
    out = [by.pop(b["id"], b) for b in blocks if b["id"] not in drop]
    return out + [b for b in put if b["id"] in by]


def seen(b: dict) -> dict:
    """A block as the screen receives it: one placed in beats (timeline.in_beats: "atBeat", "endBeat") without its seconds,
    which the screen works out from the song's tempo map (Blocks.js `timed`), so a tempo change leaves its text as
    it was and its row is not sent again."""
    if "atBeat" not in b:
        return b
    drop = ("t", "dur") if "endBeat" in b else ("t",)
    return {k: v for k, v in b.items() if k not in drop}


def text(blocks: list) -> str:
    """A whole list of blocks as the screen receives it (JSON; fails loudly on anything that is not plain data)."""
    return json.dumps([seen(b) for b in blocks], separators=(",", ":"), allow_nan=False)


class Texts:
    """The JSON text of the lists last sent, by key: the very same list is never written twice."""

    def __init__(self):
        self._held: dict = {}

    def of(self, key, blocks: list) -> str:
        held = self._held.get(key)
        if held is None or held[0] is not blocks:
            held = self._held[key] = (blocks, text(blocks))
        return held[1]

    def keep(self, keys):
        self._held = {k: v for k, v in self._held.items() if k in keys}


class RowBlocks:
    """The arrangement rows' blocks: the whole list the row model holds for each row, and the rows patched since."""

    def __init__(self):
        self.held: dict[str, list] = {}
        self.patched: set[str] = set()
        self._texts = Texts()

    def send(self, rows: list[dict], before: list[dict] | None):
        """For the rows now and the rows the screen shows (`before`): ({row id: the model's blocks, as JSON text},
        [(id, gone, put)], [ids whose patch the screen drops])."""
        prev = {r["id"]: r.get("blocks", []) for r in before or []}
        model, patches, resets = {}, [], []
        for r in rows:
            k, now = r["id"], r.get("blocks", [])
            if k in self.held and prev.get(k) is now:    # a row the change did not touch: its very same list
                model[k] = self.held[k]
                continue
            p = diff(prev.get(k), now) if k in self.held else None
            if p is None:
                model[k] = self.held[k] = now
                if k in self.patched:
                    self.patched.discard(k)
                    resets.append(k)
                continue
            model[k] = self.held[k]
            if p[0] or p[1]:
                patches.append((k, *p))
                self.patched.add(k)
        self.held = {k: v for k, v in self.held.items() if k in model}
        self.patched &= set(model)
        self._texts.keep(model)
        return {k: self._texts.of(k, v) for k, v in model.items()}, patches, resets
