"""Changes share the unchanged parts of the document with the version before (edits.fork). The thing that must
never happen silently: making a new version changes an old one (undo, versions and saved hashes read them)."""
from rostrum_core import Who, toy
from rostrum_core import edits as E
from rostrum_core.storage import canonical, doc_hash

SAM, AGENT = Who.person("sam"), Who.agent("claude-code")


def test_a_new_version_never_changes_an_old_one():
    doc = toy.sample()
    kept = [(doc.data, canonical(doc.data))]

    def keep():
        kept.append((doc.data, canonical(doc.data)))

    doc.apply({"op": "layer.rename", "target": ["card"], "args": {"name": "Hero"}}, AGENT); keep()
    with doc.gesture("Move card", SAM) as g:
        for v in (10, 20, 30):
            g.preview({"op": "layer.move", "target": ["card"], "args": {"x": v}})
    keep()
    doc.apply({"op": "layer.add", "args": {"type": "rect", "id": "box"}}, AGENT); keep()
    doc.apply({"op": "layer.remove", "target": ["key"]}, AGENT); keep()
    doc.undo(AGENT); keep()
    doc.redo(AGENT); keep()
    for data, text in kept:
        assert canonical(data) == text
    for c in doc.history.changes:
        assert c.hash_after == doc_hash(doc.at_step(c.seq))

    old = doc.data                                   # a nested field and a move, straight through a fork
    before = canonical(old)
    work, idx = E.fork(old, doc.kind.lists, doc._index())
    E.apply(work, doc.kind.lists, E.Set("card", ["look", "tint"], "red"), "t", idx)
    E.apply(work, doc.kind.lists, E.Move("card", (), ("root", "layers", 0)), "t", idx)
    assert canonical(old) == before and work["layers"][0]["look"] == {"tint": "red"}
