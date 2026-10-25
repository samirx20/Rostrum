"""A row's or the roll's blocks sent to the screen as differences: the ids gone and the blocks new or changed.

Each read of a QML list copies all of it, so sending a drum row's 300 hits again for one hit added cost a few ms per
list and grew with the song (3,000 blocks: ~27 ms, M4). A small change goes as a patch (`diff`), which the screen
applies to the list it shows (qml/Blocks.js, the same rule as `apply` here); a big one (most blocks moved, another
track) goes whole. The arrangement's row model keeps the last whole list sent for each row (`held`): a patched row
leaves the model's value as it was, and when a whole list follows, a row the screen had patched is told to drop its
patch (`resets`), so the screen shows the model's value again even when that value did not change.
"""
from __future__ import annotations

MAX = 64            # changed blocks a patch may carry; more, and the whole list goes


def diff(old: list | None, new: list) -> tuple[list, list] | None:
    """(ids gone, blocks new or changed) taking `old` to `new`; None when it is cheaper to send `new` whole."""
    if old is None:
        return None
    was = {b["id"]: b for b in old}
    ids = {b["id"] for b in new}
    gone = [i for i in was if i not in ids]
    put = [b for b in new if was.get(b["id"]) != b]
    n = len(gone) + len(put)
    return (gone, put) if n <= MAX and n < max(len(new), 1) else None


def apply(blocks: list, gone: list, put: list) -> list:
    """What the screen does with a patch (Blocks.js): changed blocks in their place, new ones at the end."""
    drop, by = set(gone), {b["id"]: b for b in put}
    out = [by.pop(b["id"], b) for b in blocks if b["id"] not in drop]
    return out + [b for b in put if b["id"] in by]


class RowBlocks:
    """The arrangement rows' blocks: the whole list the row model holds for each row, and the rows patched since."""

    def __init__(self):
        self.held: dict[str, list] = {}
        self.patched: set[str] = set()

    def send(self, rows: list[dict], before: list[dict] | None):
        """For the rows now and the rows the screen shows (`before`): ({row id: the model's blocks}, [(id, gone, put)],
        [ids whose patch the screen drops])."""
        prev = {r["id"]: r.get("blocks", []) for r in before or []}
        model, patches, resets = {}, [], []
        for r in rows:
            k, now = r["id"], r.get("blocks", [])
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
        return model, patches, resets
