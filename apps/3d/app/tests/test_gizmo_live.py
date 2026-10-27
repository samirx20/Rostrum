"""A live gizmo drag (gizmo_live.py): what would break silently is the window's view showing the item somewhere else
than where the drop puts it (the pivot resolved differently from compile.py), a drag going live where the view can't
show it exactly, or the view falling behind the pointer. No viewport or engine: a stand-in link."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND, fields as F  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d import gizmo_live as live  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402

SRC = '''
box = mesh("box", shape="box", x=0.4, y=0.5, z=-0.2, rx=20, ry=35, sx=1.5, sy=0.5, px=0.1, py=-0.2, pz=0.3)
ball = mesh("ball", shape="sphere", x=1, aim="item", aimItem="box")
cam = camera("cam", z=3, y=0.6)
shot("s", camera=cam, fps=10, start=0, end=20)
'''


@pytest.fixture
def bridge():
    QGuiApplication.instance() or QGuiApplication([])
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    b = Bridge3D(doc, viewport=None)
    yield b
    b.close()


def _node(scene, id_):
    stack = list(scene["items"])
    while stack:
        n = stack.pop()
        if n["id"] == id_:
            return n
        stack += n.get("children", [])


def test_the_live_move_is_the_place_the_drop_compiles_to(bridge):
    it = bridge.doc.item("box")
    props = _node(bridge.scene(), "box")["props"]
    sent = live.fields(it, {p.name: it.get(p.name, p.default) for p in F.FIELDS["mesh"]})
    assert sent == pytest.approx({k: props[k] for k in sent}, abs=1e-5)


def test_live_only_where_the_view_can_show_it_exactly(bridge):
    vp = SimpleNamespace(link=object(), cam=SimpleNamespace(mode="free", camera="cam", light=""))
    ctx = lambda id_: {"it": bridge.doc.item(id_), "mesh": False, "parent": None}  # noqa: E731
    assert live.why_not(bridge, vp, ctx("ball")) != ""            # it aims: its turn is worked out per frame
    assert live.why_not(bridge, vp, ctx("box")) != ""             # the ball aims at it
    assert live.why_not(bridge, vp, ctx("cam")) == ""
    assert live.why_not(bridge, SimpleNamespace(link=None, cam=vp.cam), ctx("cam")) != ""   # the engine program's view
    assert live.why_not(bridge, vp, {**ctx("cam"), "mesh": True}) != ""


def test_one_xform_on_its_way_the_newest_waits_and_a_refusal_falls_back():
    sent, refused = [], []
    link = SimpleNamespace(xform=lambda item, f, then: sent.append((f["x"], then)))
    s = live.Sender(link, refused.append)
    for x in (1.0, 2.0, 3.0):
        s.send("a", {"x": x})
    assert [x for x, _ in sent] == [1.0]                          # one on its way; 3 replaced 2
    sent[0][1]({"ok": True})
    assert [x for x, _ in sent] == [1.0, 3.0]
    sent[1][1]("3D view refused it: xform.item: no item")
    assert refused and not live._REFUSED[0]                       # this drag only; not an older build
