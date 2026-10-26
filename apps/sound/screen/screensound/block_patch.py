"""A row's or the roll's blocks sent to the screen as differences: the ids gone, the blocks new or changed, and the
blocks only moved, as "these ids moved by d" (`by`).

Each read of a QML list copies all of it, so sending a drum row's 300 hits again for one hit added cost a few ms per
list and grew with the song (3,000 blocks: ~27 ms, M4). Any change of a list the screen has goes as a patch (`diff`,
one JSON text), which the screen applies to the list it shows (qml/Blocks.js, the same rule as `apply` here): a
whole-song Right is a number per row ("every block moved by d": no ids, which the screen looked up one by one), against
~1 MB of rows parsed and re-timed again: 0.3-0.5 s of a whole-song Right, its undo, Esc of a Repeat preview. A block counts as moved only when
it is the old block with its place shifted by exactly `d` and everything else equal (the screen adds the same `d` in
the same floating point; anything else goes whole in `put`). The arrangement's row model keeps the last whole list
sent for each row (`held`): a patched row leaves the model's value as it was. When a row comes back to that very list
(Esc of a preview, undo back to it: the same block objects, block_memo.py), the screen is told to drop its patch
(`resets`) and shows the list it parsed then: the exact inverse, sent as nothing but the row's id.

A whole list goes as JSON text (`text`), which the screen parses once (Blocks.js `parse`): handing Qt a list of
dicts converted every block field by field (3,352 notes: ~150-250 ms of a whole-song Right or Esc), the text costs a
few ms each way. Made once per list (the same list object is the same text).
"""
from __future__ import annotations

import json
from operator import is_

from .block_memo import same_ends

_GONE = object()


class Patch:
    """What takes the list the screen shows to the new one: `gone` ids, `put` blocks (new or changed), `by`
    {(field, d): [ids]} (moved only: "beats" adds d to atBeat and endBeat, "secs" to t), `changed` (the new blocks
    of `put` and `by`: what the roll looks the selection up in)."""

    def __init__(self, gone, put, by, changed, every=False):
        self.gone, self.put, self.by, self.changed = gone, put, by, changed
        self.every = every          # every block of the list moved by the one (field, d) in `by`: sent without ids

    def __bool__(self):
        return bool(self.gone or self.changed)

    def text(self) -> str:
        return json.dumps({"gone": self.gone, "put": [seen(b) for b in self.put],
                           "by": [[f, d, None if self.every else ids] for (f, d), ids in self.by.items()]},
                          separators=(",", ":"), allow_nan=False)


def moved(old: dict, new: dict):
    """(field, d) when `new` is `old` shifted by d along its place and equal in all else as the screen gets it
    (`seen`); (field, 0.0) when the screen sees no difference; None for any other change."""
    if ("atBeat" in new) != ("atBeat" in old) or ("endBeat" in new) != ("endBeat" in old) or len(new) != len(old):
        return None
    if "atBeat" in new:
        field, d = "beats", new["atBeat"] - old["atBeat"]
        if old["atBeat"] + d != new["atBeat"] or ("endBeat" in new and old["endBeat"] + d != new["endBeat"]):
            return None
        skip = ("t", "dur", "atBeat", "endBeat") if "endBeat" in new else ("t", "atBeat")
    else:
        field, d = "secs", new["t"] - old["t"]
        if old["t"] + d != new["t"]:
            return None
        skip = ("t",)
    for k, v in new.items():
        if k not in skip and old.get(k, _GONE) != v:
            return None
    return field, d


def diff(old: list | None, new: list) -> Patch | None:
    """The patch taking `old` to `new`; None when there is no `old` (send `new` whole). A block the edit did not
    touch is the very same object in both (block_memo.py): only what lies between the lists' same ends is compared,
    so a patch costs what changed, not the track's length."""
    if old is None:
        return None
    a, b = same_ends(new, old)
    was = {x["id"]: x for x in old[a:len(old) - b]}
    mid = new[a:len(new) - b]
    ids = {x["id"] for x in mid}
    gone = [i for i in was if i not in ids]
    put, by, changed = [], {}, []
    for x in mid:
        o = was.get(x["id"])
        if o is x:
            continue
        m = moved(o, x) if o is not None else None
        if m is None:
            put.append(x)
            changed.append(x)
        elif m[1] != 0:
            by.setdefault(m, []).append(x["id"])
            changed.append(x)
    every = not gone and not put and len(by) == 1 and len(changed) == len(new) == len(old)
    return Patch(gone, put, by, changed, every)


def apply(blocks: list, p: dict) -> list:
    """What the screen does with a patch (`Patch.text` read back; Blocks.js): moved and changed blocks in their
    place, new ones at the end. A moved id the list doesn't have fails loudly (the screen and the song disagree)."""
    at = {b["id"]: b for b in blocks}
    put = list(p["put"])
    for field, d, ids in p["by"]:
        for i in ids if ids is not None else list(at):
            o = dict(at[i])
            if field == "beats":
                o["atBeat"] += d
                if "endBeat" in o:
                    o["endBeat"] += d
            else:
                o["t"] += d
            put.append(o)
    drop, by = set(p["gone"]), {b["id"]: b for b in put}
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
    """The arrangement rows' blocks: the whole list the row model holds for each row (`held`), the list the screen
    shows (`shown`: the held one, patched since for the rows in `patched`)."""

    def __init__(self):
        self.held: dict[str, list] = {}
        self.shown: dict[str, list] = {}
        self.patched: set[str] = set()
        self._order: list[str] = []
        self._texts = Texts()

    def send(self, rows: list[dict]):
        """For the rows now: ({row id: the model's blocks, as JSON text}, [(id, patch text)], [ids whose patch the
        screen drops]). Rows that came, went or moved go whole (a row's patch lives on the screen part that showed
        it, which may now show another row): every patched row is told to drop its patch."""
        order = [r["id"] for r in rows]
        whole, self._order = order != self._order, order
        model, patches, resets = {}, [], []
        for r in rows:
            k, now = r["id"], r.get("blocks", [])
            held = self.held.get(k)
            if held is None or (whole and now is not held):
                model[k] = self.held[k] = self.shown[k] = now
                if k in self.patched:
                    self.patched.discard(k)
                    resets.append(k)
                continue
            model[k], shown = held, self.shown[k]
            if shown is now:                              # a row the change did not touch: its very same list
                continue
            if len(now) == len(held) and all(map(is_, now, held)):
                self.shown[k] = held                      # back to the list the model holds (Esc of a preview,
                if k in self.patched:                     # an undo back to it): the screen drops its patch
                    self.patched.discard(k)
                    resets.append(k)
                continue
            p = diff(shown, now)
            self.shown[k] = now
            if p:
                patches.append((k, p.text()))
                self.patched.add(k)
        self.held = {k: v for k, v in self.held.items() if k in model}
        self.shown = {k: v for k, v in self.shown.items() if k in model}
        self.patched &= set(model)
        self._texts.keep(model)
        return {k: self._texts.of(k, v) for k, v in model.items()}, patches, resets
