"""An agent checks what its edits really did with inspect_note_changes: a wrong count or a missed change would mislead it
silently. Compared before its own last steps, against a history step and a saved version."""
from rostrum_core import Document, Who
from rostrum_core.mcp import App, Runtime

from rostrum_sound import KIND, run_source
from rostrum_sound.mcp.server import sound_tools

SONG = """
tempo(120)
a = track("a", synth="saw")
for n in range(8):
    a.note("C4", at=beat(n), dur=beats(1), vel=0.6)
d = track("d", kit="drums")
for b in range(4):
    d.hit("kick", at=beat(b))
"""


def test_note_changes_since_my_steps_a_step_and_a_version():
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SONG, "song.py"))
    ids = [n["id"] for n in doc.item("a")["notes"]]
    start = doc.seq
    doc.mark_version("first")
    rt, me = Runtime(App("rostrum-sound", {"song": doc}), sound_tools()), Who.agent("test")
    other = Who.person()
    doc.apply({"op": "note.set", "target": [ids[0]], "args": {"pitch": "E4"}}, other)       # the person's, before mine
    for op in ({"op": "note.set", "target": [ids[1]], "args": {"vel": 0.9}},
               {"op": "note.move", "target": [ids[2]], "args": {"by": {"beats": 1}}},
               {"op": "note.duplicate", "target": ids[6:8], "args": {"by": {"beats": 8}}}):
        assert rt.call("edit_document", {"ops": [op]}, me)[0]["ok"]

    mine = rt.call("inspect_note_changes", {"since": {"mine": 3}}, me)[0]
    assert mine["ok"], mine
    assert (mine["data"]["added"], mine["data"]["removed"], mine["data"]["changed"]) == (2, 0, 2)
    assert set(mine["data"]["tracks"]["a"]["changed"]) == {ids[1], ids[2]}
    assert "d" not in mine["data"]["tracks"]                                               # the drums didn't change

    whole = rt.call("inspect_note_changes", {"since": start}, me)[0]["data"]
    assert whole["changed"] == 3 and whole["added"] == 2                                   # the person's E4 counts too
    assert rt.call("inspect_note_changes", {"since": {"version": "first"}}, me)[0]["data"]["tracks"] == whole["tracks"]
    upto = rt.call("inspect_note_changes", {"since": start, "until": start + 1}, me)[0]["data"]
    assert upto["tracks"] == {"a": {"added": [], "removed": [], "changed": [ids[0]]}}
    narrow = rt.call("inspect_note_changes", {"since": start, "from": {"bar": 2}}, me)[0]["data"]
    assert ids[0] not in narrow["tracks"]["a"]["changed"]                                  # bar 1 is left out
