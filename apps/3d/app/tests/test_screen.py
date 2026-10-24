"""What would break silently on the 3D screen: an inspector edit on an animated field keys it at the playhead (never
the hidden still value) through value.set; a key drag on the timeline is one undo step; a duplicate gets new ids all the
way down and is one undo step; a cancelled render is never reported as done. No viewport or engine."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_core.keys import keys_of  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402
from screen3d.render_job import CANCELLED  # noqa: E402

SRC = '''
cam = camera("cam", z=3)
cam.key("x", {0: 0, 1: 1})
mesh("box", shape="box", y=0.5)
shot("s", camera=cam, fps=10, start=0, end=2)
'''


@pytest.fixture
def bridge():
    QGuiApplication.instance() or QGuiApplication([])
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    b = Bridge3D(doc, viewport=None)
    yield b
    b.close()


def test_edit_at_the_playhead_goes_through_value_set(bridge):
    bridge.select("cam")
    bridge.setFrame(5)                                         # 0.5 s
    still = bridge.doc.item("cam")["x"]
    assert bridge.setValue("x", 0.25)
    cam = bridge.doc.item("cam")
    assert [(k["t"], k["v"]) for k in keys_of(cam, "x")] == [(0.0, 0), (0.5, 0.25), (1.0, 1)]
    assert cam["x"] == still
    assert bridge.doc.history.changes[-1].calls[0]["op"] == "value.set"
    bridge.select("box")
    assert bridge.setValue("y", 0.75) and bridge.doc.item("box")["y"] == 0.75     # still field: changes in place
    assert not keys_of(bridge.doc.item("box"), "y")


def test_a_scrub_and_a_key_drag_are_one_undo_step_each(bridge):
    bridge.select("box")
    n = len(bridge.doc.history.changes)
    for v in (0.6, 0.7, 0.8):
        bridge.scrub("y", v)
    bridge.endScrub()
    assert len(bridge.doc.history.changes) == n + 1 and bridge.doc.item("box")["y"] == 0.8

    assert bridge.beginKeyDrag("cam.x.k1000")
    for f in (11, 13, 15):
        bridge.keyDragTo(f / 10)                 # seconds (fps 10)
    bridge.endDrag()
    assert len(bridge.doc.history.changes) == n + 2
    assert [k["t"] for k in keys_of(bridge.doc.item("cam"), "x")] == [0.0, 1.5]
    bridge.undo()
    assert [k["t"] for k in keys_of(bridge.doc.item("cam"), "x")] == [0.0, 1.0]


def test_duplicate_gets_new_ids_all_the_way_down_in_one_undo_step(bridge):
    bridge.doc.apply([{"op": "group.add", "args": {"id": "g"}}, {"op": "mesh.add", "args": {"id": "m", "into": "g"}}], bridge.who)
    bridge.doc.apply([{"op": "key.add", "target": ["m"], "args": {"prop": "x", "t": 1, "v": 2}}], bridge.who)
    before = len(bridge.doc.history.changes)
    bridge.select("g")
    bridge.adder.duplicate()
    assert len(bridge.doc.history.changes) == before + 1 and bridge.selected == "group_1"
    copy = bridge.doc.item("group_1")["children"][0]
    assert copy["id"] != "m" and copy["keys"][0]["id"].startswith(copy["id"] + ".x.")
    bridge.undo()
    assert not bridge.doc.has("group_1") and bridge.doc.has("g")


def test_cancel_ends_the_engine_process_and_never_says_done(bridge, monkeypatch):
    import threading

    import screen3d.render_job as J

    class Proc:
        killed = False
        poll = staticmethod(lambda: None)
        def kill(self): Proc.killed = True

    class Engine:                                       # a "process" that never answers
        proc = Proc()
        def close(self): pass

    started, release = threading.Event(), threading.Event()

    def hang(*a, **k):
        started.set()
        release.wait(5)
        raise RuntimeError("engine ended without a reply")
    monkeypatch.setattr(J, "still", hang)
    job = bridge.render
    job._make_engine = Engine
    job.start()
    assert started.wait(5) and job.state == "running"
    job.cancel()
    release.set()
    assert job.wait(5)
    QGuiApplication.processEvents()
    assert Proc.killed and job.state == "" and job.note == CANCELLED and job.picture == ""


def test_render_from_the_screen_makes_a_picture_and_its_record(tmp_path):
    """The Render button once failed every time (its stand-in for the document lacked what the manifest reads): a render
    asked for on the screen ends as a picture on disk and a manifest naming the step and state it shows."""
    import json

    class Engine:                                       # a core that draws a 1-pixel picture per requested file
        proc = None
        def ensure_scene(self, scene): return True
        def render(self, progress=None, **req):
            for k in ("png", "exr"):
                if k in req:
                    Path(req[k]).write_bytes(b"x")
            return {"ok": True, "frames": [{"frame": req["frame"], "ms": 5}], "renderer": "cycles", "timing": {}}
        def close(self): pass

    QGuiApplication.instance() or QGuiApplication([])
    doc = Document.new(KIND, folder=tmp_path, item="p")
    doc.run_script("s.py", run_source(SRC, "s.py"))
    doc.save()
    b = Bridge3D(doc, viewport=None)
    try:
        b.render._make_engine = Engine
        b.render.start()
        assert b.render.wait(10)
        QGuiApplication.processEvents()
        assert b.render.state == "done", b.render.note
        assert Path(b.render.path).is_file()
        record = json.loads((Path(b.render.path).parent / "manifest.json").read_text(encoding="utf-8"))
        assert record["source"]["history_entry"] == doc.seq and record["source"]["shot"] == "s"
    finally:
        b.close()


def test_a_scripted_run_opens_a_scratch_copy_never_the_real_project(tmp_path):
    """The A8 audit's test sphere was saved into the real sample: a scripted --doc must edit a copy only."""
    from rostrum_core import userhome
    from screen3d.scratch_doc import isolated

    real = tmp_path / "real"
    doc = Document.new(KIND, folder=real, item="p")
    doc.run_script("s.py", run_source(SRC, "s.py"))
    doc.save()
    assert userhome.scripted()                                  # pytest counts as a scripted run
    mine = isolated(real, "p", KIND.ext)
    assert mine != real and (mine / "docs" / f"p{KIND.ext}").is_file()
    copy = Document.open(mine, "p", KIND)
    copy.apply([{"op": "mesh.add", "args": {"id": "extra", "shape": "sphere"}}], Bridge3D(copy, viewport=None).who)
    copy.save()
    assert not Document.open(real, "p", KIND).has("extra") and Document.open(mine, "p", KIND).has("extra")


def test_context_menu_never_holds_more_than_six_and_only_what_applies(bridge):
    for item in ("", "box", "cam", "s"):
        assert len(bridge.contextEntries(item)) <= 6
    assert [e["value"] for e in bridge.contextEntries("")] == ["home", "shot"]
    assert [e["value"] for e in bridge.contextEntries("cam")] == ["duplicate", "delete"]


def test_timing_shows_only_on_the_animate_page(bridge):
    """A setting valid only while animating (Timing) is absent on Build and comes with the Animate page (rows re-evaluate)."""
    bridge.select("cam")
    names = lambda: [r["id"] for r in bridge._rows() if r.get("holds")]  # noqa: E731
    assert "timing" not in names()
    bridge.setPage("animate")
    assert "timing" in names()
    bridge.setPage("build")
    assert "timing" not in names()
