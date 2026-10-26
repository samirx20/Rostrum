"""Many items in or out as one edit (edits.Many) give exactly what the edits one by one give: the same tree, the same
records (each item's sibling), and its reverse puts the tree back exactly, through a fork or in place, nested lists too."""
import random

from rostrum_core import edits as E
from rostrum_core.storage import doc_hash
from rostrum_core.tree import index

LISTS = {"doc": ["tracks"], "track": ["notes"]}


def _doc():
    return {"id": "root", "type": "doc", "tracks": [{"id": f"t{t}", "type": "track", "notes": [
        {"id": f"t{t}.n{i}", "type": "note", "at": i} for i in range(20)]} for t in range(3)]}


def _one_by_one(edits):
    data = _doc()
    idx = index(data, LISTS)
    return data, [E.apply(data, LISTS, e, "x", idx) for e in edits]


def _many(edits, forked=True):
    data = _doc()
    if not forked:
        return data, E.apply(data, LISTS, E.Many(edits), "x")
    work, idx = E.fork(data, LISTS)
    done = E.apply(work, LISTS, E.Many(edits), "x", idx)
    assert {i: (l.parent, l.index) for i, l in index(work, LISTS).items()} == {i: (l.parent, l.index) for i, l in idx.items()}
    return work, done


def _back(data, done):
    work, idx = E.fork(data, LISTS)
    E.apply(work, LISTS, E.from_dict(E.to_dict(E.reverse(done))), "x", idx)   # through its history line
    assert doc_hash(work) == doc_hash(_doc())


def test_many_inserts_and_removes_match_one_by_one_and_reverse_exactly():
    rnd = random.Random(7)
    for _ in range(150):
        ids = [n["id"] for t in _doc()["tracks"] for n in t["notes"]]
        ins = []
        for k in range(rnd.randint(2, 30)):
            t = f"t{rnd.randrange(3)}"
            here = [i for i in ids if i.startswith(t + ".")]
            r = rnd.random()
            after = E.NO_AFTER if r < .3 else None if r < .4 else rnd.choice(here + ["gone"])
            ins.append(E.Insert(f"{t}.m{k}", t, "notes", rnd.randrange(-2, 40), {"id": f"{t}.m{k}", "type": "note"}, after))
            ids.append(f"{t}.m{k}")
        want, rec = _one_by_one(ins)
        for forked in (True, False):
            got, done = _many(ins, forked)
            assert doc_hash(got) == doc_hash(want) and [(e.id, e.after) for e in done.edits] == [(e.id, e.after) for e in rec]
            _back(got, done)
        rem = [E.Remove(i) for i in rnd.sample([n["id"] for t in _doc()["tracks"] for n in t["notes"]], rnd.randint(2, 40))]
        want, rec = _one_by_one(rem)
        got, done = _many(rem)
        assert doc_hash(got) == doc_hash(want) and [(e.id, e.after) for e in done.edits] == [(e.id, e.after) for e in rec]
        _back(got, done)


def test_a_track_and_notes_on_it_go_out_and_come_back_in_one_edit():
    got, done = _many([E.Remove("t1.n3"), E.Remove("t1"), E.Remove("t0.n1")])
    assert [t["id"] for t in got["tracks"]] == ["t0", "t2"]
    _back(got, done)
