"""A row's blocks on the screen must always be exactly the song's, whichever way they got there: a patch, a drop back
to the list the model holds, or a swap back to the list shown a step before (an undo, then its redo: block_patch.py
`backs`, block_memo.py handing back the very blocks of items an edit took away). A wrong swap would show notes that
are not in the song, and only a person looking closely would see it."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screensound.block_memo import BlockMemo  # noqa: E402
from screensound.block_patch import RowBlocks, apply, seen  # noqa: E402


def note(i, at, pitch=60):
    return {"id": f"n{i}", "at": at, "pitch": pitch}


class Screen:
    """The lane's rule (LaneBlocks.qml): `patched` over the parsed model list, `was` the list shown before."""

    def __init__(self):
        self.parsed, self.patched, self.was = [], None, None

    def shown(self):
        return self.patched if self.patched is not None else self.parsed

    def show(self, lst):
        self.patched, self.was = lst, self.patched

    def take(self, sent, rid):
        model, patches, resets, backs = sent
        if model[rid] is not self.__dict__.get("text"):
            self.text, self.parsed, self.patched, self.was = model[rid], json.loads(model[rid]), None, None
        for k in resets:
            self.show(None)
        for k in backs:
            self.show(self.was)
        for k, p in patches:
            self.show(apply(self.shown(), json.loads(p)))


def test_undo_and_redo_of_many_adds_and_removes_show_the_song():
    memo, rows, screen = BlockMemo(), RowBlocks(), Screen()
    make = lambda x: {"id": x["id"], "t": x["at"], "dur": 0.5, "keys": [x["pitch"]]}   # noqa: E731
    memo.follow("clock", {"tr"})
    full = [note(i, i * 0.5, 60 + i % 12) for i in range(300)]
    moved = [{**n, "at": n["at"] + 1.0} for n in full]
    copies = [note(1000 + i, 200 + i * 0.5, 61) for i in range(300)]
    steps = [full, moved, [], [dict(n) for n in moved], moved + copies, list(moved), moved + copies,
             moved[:10] + moved[20:], list(moved), [], list(moved), full]
    for items in steps:
        blocks = memo.made(("tr", "notes"), items, make)
        screen.take(rows.send([{"id": "tr", "blocks": blocks}]), "tr")
        got = sorted(screen.shown(), key=lambda b: b["id"])
        assert got == sorted(map(seen, blocks), key=lambda b: b["id"])


def test_items_put_back_equal_get_their_very_blocks_again():
    memo = BlockMemo()
    memo.follow("clock", {"tr"})
    make = lambda x: {"id": x["id"], "t": x["at"]}   # noqa: E731
    full = [note(i, float(i)) for i in range(50)]
    before = memo.made(("tr", "notes"), full, make)
    memo.made(("tr", "notes"), [], make)
    after = memo.made(("tr", "notes"), [dict(n) for n in full], make)
    assert all(a is b for a, b in zip(after, before))
    memo.made(("tr", "notes"), [], make)
    memo.follow("another clock", {"tr"})            # the clock moved: nothing held is handed out as it was
    assert all(a is not b for a, b in zip(memo.made(("tr", "notes"), full, make), before))
