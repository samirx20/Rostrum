"""Going back to a History row and forward again must give back the very same song (a wrong replay would lose work
silently), and an agent may go back only over its own steps."""
import copy

from rostrum_core import Document, Who
from rostrum_core.mcp import App, Runtime

from rostrum_sound import KIND, history_go, run_source
from rostrum_sound.mcp.server import sound_tools

SONG = """
tempo(120)
a = track("a", synth="saw")
for n in range(8):
    a.note("C4", at=beat(n), dur=beats(1), vel=0.6)
"""


def test_back_to_a_row_and_forward_again_restore_the_same_song():
    doc, me = Document.new(KIND), Who.person()
    doc.run_script("song.py", run_source(SONG, "song.py"))
    ids = [n["id"] for n in doc.item("a")["notes"]]
    row, then = doc.seq, copy.deepcopy(doc.data)
    doc.apply({"op": "note.set", "target": [ids[0]], "args": {"pitch": "E4"}}, me)
    doc.apply({"op": "note.move", "target": [ids[1]], "args": {"by": {"beats": 1}}}, me)
    newest, now = doc.seq, copy.deepcopy(doc.data)

    assert len(history_go.go_to(doc, row, me)) == 1 and doc.data == then           # back: one step
    assert history_go.go_to(doc, newest, me) and doc.data == now                    # the newest row: all brought back
    history_go.go_to(doc, row, me)
    assert history_go.go_to(doc, row + 1, me) and doc.data["tracks"][0]["notes"][0]["pitch"] == "E4" \
        and doc.data != now                                                         # one row forward: only that step
    doc.undo(me)                                                                    # Ctrl+Z takes back the going
    assert doc.data == then


def test_an_agent_goes_back_only_over_its_own_steps():
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SONG, "song.py"))
    ids = [n["id"] for n in doc.item("a")["notes"]]
    rt, agent = Runtime(App("rostrum-sound", {"song": doc}), sound_tools()), Who.agent("test")
    row = doc.seq
    for vel in (0.9, 0.3):
        assert rt.call("edit_document", {"ops": [{"op": "note.set", "target": [ids[0]], "args": {"vel": vel}}]}, agent)[0]["ok"]
    assert rt.call("edit_history_go", {"to": row + 1}, agent)[0]["ok"] and doc.item(ids[0])["vel"] == 0.9
    doc.apply({"op": "note.set", "target": [ids[3]], "args": {"vel": 0.2}}, Who.person())
    refused = rt.call("edit_history_go", {"to": row}, agent)[0]
    assert not refused["ok"] and "Your undo is yours" in refused["summary"] and doc.item(ids[0])["vel"] == 0.9
