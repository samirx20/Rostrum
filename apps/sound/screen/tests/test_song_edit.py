"""What would break silently when the song's music map is edited on the screen: a tempo-change or section-edge drag
is one undo step and keeps the time's form (beats stay beats, a marker stays a marker), and a project item as the
picture resolves to its newest render (a newer one is picked up)."""
import json
import sys
from pathlib import Path

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
