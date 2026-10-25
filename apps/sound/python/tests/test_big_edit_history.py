"""A big edit's history stays exact (the edit step copies a new item once, shared by the song and its history): undo of
a Ctrl+D on hundreds of notes gives back the very song, redo the very copy, and the history replayed from the start
gives the same; a script's re-run (which writes in place) keeps its records clean and never wipes a person's move."""
import copy

from rostrum_core import Document, Who
from rostrum_core.storage import doc_hash

from rostrum_sound import KIND, run_source

P = Who.person()
SONG = """
tempo(120)
a = track("a", synth="saw")
for n in range(240):
    a.note(["C4", "E4", "G4"][n % 3], at=beat(n * 0.5), dur=beats(0.5), vel=0.6)
d = track("d", kit="drums")
for b in range(120):
    d.hit("kick" if b % 2 == 0 else "snare", at=beat(b))
"""


def _song(src=SONG):
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(src, "song.py"))
    return doc


def _same_as_history(doc):
    assert doc.at_step(doc.seq) == doc.data and doc_hash(doc.at_step(doc.seq)) == doc_hash(doc.data)


def test_undo_of_a_big_duplicate_restores_exactly_and_redo_brings_the_same_copy():
    doc = _song()
    by = {k: [i["id"] for t in doc.data["tracks"] for i in t.get(k + "s", [])] for k in ("note", "hit")}
    before = copy.deepcopy(doc.data)
    doc.apply([{"op": f"{k}.duplicate", "target": ids, "args": {"by": {"beats": 120}}} for k, ids in by.items()], P)
    after = copy.deepcopy(doc.data)
    assert len(doc.item("a")["notes"]) == 480
    doc.apply({"op": "note.move", "target": by["note"][:5], "args": {"by": {"beats": 1}}}, P)   # a later edit on top
    doc.undo(P)
    doc.undo(P)
    assert doc.data == before and doc_hash(doc.data) == doc_hash(before)
    doc.redo(P)
    assert doc.data == after
    _same_as_history(doc)


def test_rerun_keeps_a_persons_move_and_its_records_stay_clean():
    doc = _song()
    note = doc.item("a")["notes"][3]["id"]
    doc.apply({"op": "note.move", "target": [note], "args": {"by": {"beats": 2}}}, P)
    moved = copy.deepcopy(doc.item(note)["at"])
    rep = doc.run_script("song.py", run_source(SONG.replace("vel=0.6", "vel=0.8") + 'e = track("e", synth="saw")\n'
                                               'e.note("C3", at=beat(0), dur=beats(1))\n', "song.py"))
    assert doc.item(note)["at"] == moved and doc.item(note)["vel"] == 0.8 and rep.applied
    _same_as_history(doc)
    rerun = copy.deepcopy(doc.data)
    doc.undo(Who.script("song.py"))
    assert doc.item(note)["at"] == moved and not doc.has("e")
    doc.redo(Who.script("song.py"))
    assert doc.data == rerun
    _same_as_history(doc)


def test_a_call_that_adds_then_changes_keeps_its_record_as_added():
    doc = _song()
    op = lambda o, t, **a: {"op": o, "target": t, "args": a}    # noqa: E731
    doc.apply([op("track.add", [], id="t9", instrument="builtIn", builtIn="piano"),
               op("note.add", ["t9"], id="n9", pitch="C4", at={"beat": 0}, dur={"beats": 1}),
               op("note.set", ["n9"], vel=0.3)], P)
    made = copy.deepcopy(doc.data)
    first = doc.history.changes[-1].edits[0]
    assert first.item["id"] == "t9" and not first.item.get("notes")    # the track as added: its note is its own edit
    doc.undo(P)
    doc.redo(P)
    assert doc.data == made
    _same_as_history(doc)
