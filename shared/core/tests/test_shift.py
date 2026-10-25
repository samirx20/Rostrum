"""A uniform change of many items is one edit (edits.Shift: ids + amount), and taking it back is exact: every value
as it was, type included, even where rounding the moved value back would not give it (a whole-song nudge)."""
from rostrum_core import Document, Who, edits as E, storage, toy

SAM = Who.person("sam")


def test_a_shift_is_one_edit_and_undo_redo_and_reopen_are_exact(tmp_path):
    doc = toy.sample(tmp_path, "itm")
    doc.save()
    ids = [i["id"] for i in doc.data["layers"] if isinstance(i.get("x"), (int, float))]
    odd = {ids[0]: 0.123456789, ids[1]: 3}                         # more decimals than kept; an int stays an int
    work, idx = E.fork(doc.data, doc.kind.lists, doc.locs())
    edits = [E.apply(work, doc.kind.lists, E.Set(i, ["x"], v), "set", idx) for i, v in odd.items()]
    doc.commit(work, edits, SAM, "Set")
    before = storage.canonical(doc.data)
    work, idx = E.fork(doc.data, doc.kind.lists, doc.locs())
    done = E.apply(work, doc.kind.lists, E.Shift(ids, ["x"], 0.1, 4), "nudge", idx)
    doc.commit(work, [done], SAM, "Nudge")
    after = storage.canonical(doc.data)
    assert doc.item(ids[0])["x"] == 0.2235 and doc.item(ids[1])["x"] == 3.1 and ids[0] in done.back
    doc.undo(SAM)
    assert storage.canonical(doc.data) == before                   # exact: 0.123456789 and the int 3 back
    doc.redo(SAM)
    assert storage.canonical(doc.data) == after
    doc.save()
    again = Document.open(tmp_path, "itm", toy.KIND)               # the history line holds one edit, read back whole
    assert storage.canonical(again.data) == after and storage.canonical(again.at_step(1)) == before
    assert sum(isinstance(e, E.Shift) for c in again.history.changes for e in c.edits) == 3   # nudge, undo, redo
