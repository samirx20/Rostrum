"""Undo and redo take a step back by its own edits (the inverse of what it changed), never by rebuilding the document
from its history: whatever mix of edits, undos and redos by a person and an agent, the document must stay exactly
what replaying its whole history from the start gives (Document.at_step), and what Undo / Redo would take next (kept
per author as changes are added) and the "N changes" count must be what a walk of the whole history says."""
import random

from rostrum_core import Document, RostrumError, Who
from rostrum_core import edits as E

from rostrum2d import KIND, run_source

SRC = '''
comp("intro", duration=3)
t = text("title", body="Hi", size=200)
t.key("y", {0.2: 600, 1.0: 540})
shape("card", shape="rect", w=400, h=300)
shape("dot", shape="rect", w=40, h=40)
'''
SAM, AGENT = Who.person("sam"), Who.agent("claude-code")


def _edit(d, rnd):
    layers = [i["id"] for i in d.data["comps"][0]["layers"]] if d.data.get("comps") else []
    ids = [i["id"] for i in d.items() if i.get("type") in ("text", "rect", "shape", "group")] or layers
    lay = rnd.choice(ids)
    pick = rnd.randrange(6)
    if pick == 0:
        return {"op": "value.set", "target": lay, "args": {"prop": "x", "v": rnd.randrange(0, 1900)}}
    if pick == 1:
        return {"op": "value.set", "target": lay, "args": {"prop": "opacity", "v": rnd.random()}}
    if pick == 2:
        return {"op": "item.rename", "target": [lay], "args": {"name": f"n{rnd.randrange(99)}"}}
    if pick == 3:
        return {"op": "layer.duplicate", "target": [lay]}
    if pick == 4 and len(ids) > 2:
        return {"op": "layer.remove", "target": [lay]}
    return {"op": "value.set", "target": lay, "args": {"prop": "y", "at": rnd.choice((0.2, 1.0, 2.0)), "v": rnd.randrange(900)}}


def _walked(h, who):
    """Undo / Redo's next step by the history's own definition (OPERATIONS.md § 6), worked out from every change."""
    own = [c for c in h.changes if c.original and c.who == who]
    undo = max((c for c in own if h.done[c.seq]), key=lambda c: h.at[c.seq], default=None)
    newest = max((c.seq for c in own), default=0)
    redo = max((c for c in own if not h.done[c.seq] and h.at[c.seq] > newest), key=lambda c: h.at[c.seq], default=None)
    return undo, redo, max((c.t for c in own), default=0.0)


def _own_t(h, who) -> float:
    """Clock time of `who`'s newest original change (0 when none): what a redo is offered only after."""
    c = h.newest_own(who)
    return c.t if c is not None else 0.0


def _moved(h, mark):
    seq0, done0 = mark
    return sum(1 for c in h.changes if c.original and (h.done[c.seq] if c.seq > seq0 else h.done[c.seq] != done0.get(c.seq)))


def _blocked(h, c) -> bool:
    """Would taking `c` back (or bringing it back) be refused: a later done change by anyone touched the same."""
    mine = h.keys(c)
    return any(x.original and x.seq != c.seq and h.done[x.seq] and h.at[x.seq] > h.at[c.seq] and E.overlap(h.keys(x), mine)
               for x in h.changes)


def test_random_edits_undos_and_redos_match_the_replayed_history():
    for seed in range(6):
        rnd = random.Random(seed)
        d = Document.new(KIND)
        d.run_script("intro.py", run_source(SRC, "intro.py"))
        marks = [d.history.mark()]
        for n in range(60):
            if n == 25:
                marks.append(d.history.mark())          # a window opened mid-way counts from there
            who = SAM if rnd.random() < 0.75 else AGENT
            roll = rnd.random()
            h = d.history
            target = None if roll < 0.5 else h.last_undoable(who) if roll < 0.8 else h.last_redoable(who)
            expect = target is not None and _blocked(h, target)
            refused = False
            try:
                if roll < 0.5:
                    d.apply(_edit(d, rnd), who, join=rnd.random() < 0.3)     # some join the last (a nudge)
                elif roll < 0.8:
                    d.undo(who)
                else:
                    d.redo(who)
            except RostrumError as e:                   # a refused step changes nothing
                refused = "can't be taken back" in str(e)
            assert refused == expect, f"seed {seed}: refused {refused}, the walk says {expect}"
            assert d.data == d.at_step(d.seq), f"seed {seed}: the document drifted from its history"
            for w in (SAM, AGENT):
                h = d.history
                assert (h.last_undoable(w), h.last_redoable(w), _own_t(h, w)) == _walked(h, w), f"seed {seed}: {w}"
            assert [d.history.moved_since(m) for m in marks] == [_moved(d.history, m) for m in marks], f"seed {seed}"
