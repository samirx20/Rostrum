"""Re-running a script after changing only its tempo keeps a person's edits (AGENTS.md rule 3; critic r9: note ids are
their start in ms, so the new tempo renamed every note; the person's edited notes were held back beside the script's
new copies and played twice)."""
from rostrum_core import Document, Who

from rostrum_sound import KIND, run_source

SRC = """
tempo({t})
a = track("a", builtIn="piano")
for n in range(4):
    a.note("C4", at=beat(n), dur=beats(1), vel=0.6)
"""
S, P = Who.script("song.py"), Who.person()


def test_a_tempo_change_rerun_keeps_the_persons_edits_and_makes_no_copies():
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SRC.format(t=120), "song.py"), S)
    ids = [n["id"] for n in doc.data["tracks"][0]["notes"]]
    doc.apply([{"op": "note.set", "target": [ids[1]], "args": {"vel": 0.95}},
               {"op": "note.set", "target": [ids[2]], "args": {"pitch": "E4"}}], P)
    report = doc.run_script("song.py", run_source(SRC.format(t=90), "song.py"), S)
    notes = doc.data["tracks"][0]["notes"]
    assert not report.held and doc.data["tempo"] == 90
    assert [(n["id"], n["pitch"], n["vel"]) for n in notes] == [
        (ids[0], "C4", 0.6), (ids[1], "C4", 0.95), (ids[2], "E4", 0.6), (ids[3], "C4", 0.6)]
    doc.undo(S)
    assert doc.data["tempo"] == 120 and len(doc.data["tracks"][0]["notes"]) == 4
