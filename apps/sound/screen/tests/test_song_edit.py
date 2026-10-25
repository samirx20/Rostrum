"""What would break silently when the song's music map is edited on the screen: a tempo-change or section-edge drag
is one undo step and keeps the time's form (beats stay beats, a marker stays a marker), a time signature change
added from the song panel is one undo step at the time signature playing there, on the nearest bar line, selected, and no
second "+" there (an agent's change off a bar line is refused); a project item as the
picture resolves to its newest render (a newer one is picked up)."""
import json
import sys
from pathlib import Path

import pytest
from rostrum_core import RostrumError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screensound import picture  # noqa: E402
from screensound.steps import drag  # noqa: E402
from test_screen import bridge  # noqa: E402,F401  (the screen's fixture: a small song, a stand-in engine)


def test_tempo_and_section_edits_are_one_undo_step_each_and_keep_form(bridge):  # noqa: F811
    doc = bridge.doc
    bridge.doc.data.setdefault("markers", [])
    bridge.setTime(4.0)                                         # beat 8 at 120 bpm
    n = len(doc.history.changes)
    bridge.songDo("add_tempo", "")
    bridge.songDo("add_section", "")
    assert len(doc.history.changes) == n + 2
    tempo_id, section_id = doc.data["tempos"][0]["id"], doc.data["sections"][0]["id"]
    assert doc.item(tempo_id)["at"] == {"beat": 8.0} and doc.item(section_id)["end"] == {"beat": 24.0}
    n = len(doc.history.changes)
    drag(bridge, tempo_id, 1.0)                                 # a second later: still on a beat
    assert len(doc.history.changes) == n + 1 and doc.item(tempo_id)["at"] == {"beat": 10.0}
    bridge.beginEdge(section_id, "end")
    for f in (0.5, 1.0):
        bridge.dragBy(2.0 * f, 0, False)
    bridge.endDrag()
    assert len(doc.history.changes) == n + 2
    assert doc.item(section_id)["end"] == {"beat": 28.0} and doc.item(section_id)["at"] == {"beat": 8.0}
    bridge.undo()
    assert doc.item(section_id)["end"] == {"beat": 24.0}


def test_time_signature_change_from_the_song_panel_is_one_undo_step(bridge):  # noqa: F811
    doc = bridge.doc
    bridge.setTime(0.0)
    assert not bridge.songEdit()["canMeter"]                    # the start is the song's own time signature
    bridge.setTime(4.0)                                         # beat 8 at 120 bpm
    assert bridge.songEdit()["canMeter"]
    n = len(doc.history.changes)
    bridge.songDo("add_meter", "")
    assert len(doc.history.changes) == n + 1
    change = doc.data["meters"][-1]
    assert change["at"] == {"beat": 8.0} and (change["beatsPerBar"], change["beatUnit"]) == (4, 4)
    assert bridge.selected == change["id"] and not bridge.songEdit()["canMeter"]
    bridge.undo()
    assert not doc.data.get("meters")
    bridge.setTime(4.6)                                         # between bar lines: the nearest one (bar 3, beat 8)
    bridge.songDo("add_meter", "")
    assert doc.data["meters"][-1]["at"] == {"beat": 8.0}
    bridge.undo()
    with pytest.raises(RostrumError, match="not on a bar line"):    # an agent's change off a bar line is refused
        doc.apply([{"op": "meter.add", "target": [], "args": {"at": {"beat": 9.5}, "beatsPerBar": 6, "beatUnit": 8}}],
                  bridge.who)


def test_picture_item_link_follows_the_newest_render(tmp_path):
    for v in (1, 2):
        d = tmp_path / "renders" / "logo" / f"v{v:03d}"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"kind": "pictures"}))
        (d / f"logo-{v}.mp4").write_bytes(b"")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "logo.mtn").write_text('{"doc": {"name": "Logo"}}')
    video, why = picture.resolve("item:logo", tmp_path)
    assert Path(video).name == "logo-2.mp4" and why == ""
    assert picture.resolve("item:nope", tmp_path)[0] == "" and picture.resolve("item:logo", None)[1]


SECTIONS = '''
tempo(120); beats_per_bar(4)
key("D minor"); section("a", bar(1), bar(3)); section("b", bar(3), bar(5))
marker("cut", at=bar(3)); marker("flash", at=13.0)
bass = track("bass", builtIn="feltPiano")
for i in range(16):
    bass.note("D2", at=beat(i * 2), dur=beats(1))
bass.note("A2", at="#flash+0.5", dur=0.5)
'''


def test_a_section_drag_carries_what_it_held_at_the_press_and_replays_exactly(bridge):  # noqa: F811
    """A section dragged past notes and markers (many small steps, back and forth): only what was inside it at the
    press moves, markers stay; one change whose recorded call replays to the same song; undo and redo exact."""
    from rostrum_core import Document, Who
    from rostrum_sound import KIND, run_source
    doc = bridge.doc
    doc.run_script("song.py", run_source(SECTIONS, "song.py"))
    start, n = doc.data, len(doc.history.changes)
    assert bridge.beginDrag("section.b")
    for i in range(1, 61):                                      # 6 s later (over notes and the flash) in 0.1 s
        bridge.dragBy(i * 0.1 + (0.37 if i == 20 else 0), 0, False)   # steps, one a little too far and back
    bridge.endDrag()
    end = doc.data
    assert len(doc.history.changes) == n + 1
    calls = doc.history.changes[-1].calls
    assert calls == [{"op": "section.move", "target": ["section.b"], "args": {"by": {"beats": 12.0}}}]
    beats = sorted(x["at"]["beat"] for x in doc.item("bass")["notes"] if isinstance(x["at"], dict))
    assert beats == [0, 2, 4, 6, 16, 18, 20, 20, 22, 22, 24, 24, 26, 26, 28, 30]    # bars 3-4's notes 12 beats on, no other
    assert doc.item("bass")["notes"][-1]["at"] == "#flash+0.5"
    assert {m["name"]: m["at"] for m in end["markers"]} == {m["name"]: m["at"] for m in start["markers"]}  # markers stay
    assert end["keys"] == start["keys"]                         # the song's opening key stays
    again = Document.new(KIND)                                  # replay: the same script, then the recorded call
    again.run_script("song.py", run_source(SECTIONS, "song.py"))
    again.apply(calls, Who.person())
    assert again.data == end
    bridge.undo()
    assert doc.data == start
    bridge.redo()
    assert doc.data == end
