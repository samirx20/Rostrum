"""Undo N then redo N in order brings every state back exactly, never refused (critic r8: the second redo was refused
naming "track_1.n20000.at.beat"), including whole-song moves and a Ctrl+D on everything."""
import copy

from rostrum_core import Document, Who

from rostrum_sound import KIND, run_source

P = Who.person()
SONG = """
tempo(120)
a = track("a", synth="saw")
for n in range(200):
    a.note(["C4", "E4", "G4"][n % 3], at=beat(n * 0.5), dur=beats(0.5), vel=0.6)
d = track("d", kit="drums")
for b in range(100):
    d.hit("kick" if b % 2 == 0 else "snare", at=beat(b))
"""


def _all(doc):
    return [{"op": f"{k}.{{}}", "target": [i["id"] for t in doc.data["tracks"] for i in t.get(k + "s", [])]}
            for k in ("note", "hit")]


def _step(doc, verb, args):
    doc.apply([{**c, "op": c["op"].format(verb), "args": args} for c in _all(doc)], P, join=False)


def test_undo_n_then_redo_n_over_whole_song_moves_and_a_duplicate_is_exact():
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SONG, "song.py"))
    states = [copy.deepcopy(doc.data)]
    for verb, args in (("move", {"by": {"beats": 1}}), ("move", {"by": {"beats": 1}}), ("duplicate", {}),
                       ("move", {"by": {"beats": -1}})):
        _step(doc, verb, args)
        states.append(copy.deepcopy(doc.data))
    for n in range(4):
        doc.undo(P)
        assert doc.data == states[-2 - n]
    for n in range(4):
        doc.redo(P)
        assert doc.data == states[2 + n - 1]
    assert doc.data == doc.at_step(doc.seq)


def test_closing_with_the_repeat_box_open_saves_no_copies_and_the_song_equals_its_history(tmp_path):
    """Critic r8 must-fix 1: 448 notes became 2,240 on disk with no history step."""
    import json
    from rostrum_core import live
    doc = Document.new(KIND, folder=str(tmp_path), item="main")
    doc.run_script("song.py", run_source(SONG, "song.py"))
    doc.save()
    live.keep(doc)
    seq, before = doc.seq, copy.deepcopy(doc.data)
    g = doc.gesture("Repeat", P).__enter__()                     # Ctrl+R: the box open, its copies showing
    g.preview(lambda: [{**c, "op": "note.duplicate", "args": {"times": 4}} for c in _all(doc)[:1]], fresh=True)
    assert doc.data != before
    doc.save()
    assert json.loads((tmp_path / "docs" / f"main{KIND.ext}").read_text(encoding="utf-8"))["doc"] == before
    doc.drop_gesture()                                           # the window closes (LiveLink.close)
    doc.live.fold(always=False)
    again = Document.open(tmp_path, "main", KIND)
    assert again.data == before and again.seq == seq and doc.data == before
