"""What would break silently on the copies screen (brief 24): the right-click's Make copies / Scatter / Change near make
one undo step each and leave the right thing selected; Scatter is offered only right after a right-click on another
item; Count's drag is one undo step; the grey line under Count says how many the camera sees. No viewport or engine."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402

SRC = '''
cam = camera("cam", z=3)
mesh("bud", shape="sphere", radius=0.05, y=0.5)
mesh("plinth", shape="box", y=0.1)
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


def labels(b):
    return {e["label"]: [s["label"] for s in e["sub"]] for e in b.actions.menu()}


def test_make_copies_is_one_step_and_selected(bridge):
    bridge.select("bud")
    assert labels(bridge)["Make copies"][:3] == ["Line", "Grid", "Circle"]
    n = len(bridge.doc.history.changes)
    bridge.actions.run("copies:make:circle")
    assert (bridge.selected, bridge.doc.item(bridge.selected)["layout"]) == ("copies_1", "circle")
    assert len(bridge.doc.history.changes) == n + 1
    assert [c["id"] for c in bridge.doc.item("copies_1")["children"]] == ["bud"]


def test_scatter_only_right_after_a_right_click_on_a_surface(bridge):
    bridge.select("bud")
    bridge.menuSelect("plinth")
    assert "Scatter 'bud' on 'plinth'" in labels(bridge)
    bridge.actions.run("copies:scatter")
    assert bridge.doc.item("copies_1")["surface"] == "plinth" and bridge.selected == "copies_1"
    bridge.select("plinth")
    assert not any(k.startswith("Scatter") for k in labels(bridge))


def test_change_near_adds_a_sphere_and_follows_an_item_when_given_one(bridge):
    bridge.select("bud")
    bridge.actions.run("copies:make:line")
    bridge.select("copies_1")
    n = len(bridge.doc.history.changes)
    bridge.actions.run("copies:near:scale")
    assert len(bridge.doc.history.changes) == n + 1 and bridge.selected == "mesh_1"      # the sphere to move is selected
    assert bridge.doc.item("effector_1")["near"] == "mesh_1"
    bridge.selectMany(["copies_1", "plinth"])
    bridge.actions.run("copies:near:turn")
    assert bridge.doc.item("effector_2")["near"] == "plinth" and not bridge.doc.has("mesh_2")


def test_count_drag_without_a_live_view_is_one_undo_step(bridge):
    bridge.select("bud")
    bridge.actions.run("copies:make:line")
    n = len(bridge.doc.history.changes)
    bridge.beginScrub("count")
    for v in (8, 10, 12):
        bridge.scrub("count", v)
    bridge.endScrub()
    assert bridge.doc.item("copies_1")["count"] == 12 and len(bridge.doc.history.changes) == n + 1


def test_the_line_under_count():
    from screen3d.copies_qt import note_text
    it = {"layout": "surface", "amountBy": "count", "count": 400}
    assert note_text(it, {}, "Hero 01") == "400 copies"
    assert note_text(it, {"count": 400, "seen": 212, "camera": "cam"}, "Hero 01") == "212 of 400 in Hero 01"
    assert note_text({**it, "amountBy": "density"}, {}, "Hero 01") == ""        # a density's count is the engine's to say


def test_count_drag_with_a_live_view_sends_requests_and_changes_the_document_once(bridge):
    from types import SimpleNamespace

    class Link:
        item = object()
        sent: list = []

        def post(self, req, then, scene=None):
            self.sent.append(req)
            then({"ok": True, "count": req["copies"]["props"]["count"], "ms": 1.0})

    bridge.select("bud")
    bridge.actions.run("copies:make:line")
    bridge.viewport = SimpleNamespace(link=Link())
    n = len(bridge.doc.history.changes)
    bridge.beginScrub("count")
    for v in (8, 10, 12):
        bridge.scrub("count", v)
    assert bridge.doc.item("copies_1")["count"] == 6 and len(bridge.doc.history.changes) == n      # no document change yet
    bridge.endScrub()
    assert [r["copies"]["props"]["count"] for r in Link.sent] == [8, 10, 12]
    assert bridge.doc.item("copies_1")["count"] == 12 and len(bridge.doc.history.changes) == n + 1
    bridge.viewport = None
