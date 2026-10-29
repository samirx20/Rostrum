"""The bone's turn rings (gizmo_bone.py): what would break silently is a drag that writes the bone's still Turn (its rest
moves with it and the mesh bends nothing) or that lands as several undo steps. The drag here is gizmo_qt's own steps
(item_drag's turn, gizmo_bone.calls, one Drag); the real-window click and drag are checked by hand. No viewport or engine."""
import math
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who  # noqa: E402
from rostrum_core.keys import keys_of  # noqa: E402
from rostrum_gui.edits import Drag  # noqa: E402
from rostrum3d import KIND, aim, skin, through  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d import gizmo as G, gizmo_bone  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402
from screen3d.gizmo_drag import item_drag  # noqa: E402

SRC = '''
strap = mesh("strap", shape="capsule", radius=0.05, height=1.2)
cam = camera("cam", z=3, y=0.6)
shot("s", camera=cam, fps=10, start=0, end=20)
'''


@pytest.fixture
def bridge():
    QGuiApplication.instance() or QGuiApplication([])
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    doc.apply({"op": "bone.chain", "target": ["strap"], "args": {"points": [[0, 0, 0], [0, 0.6, 0], [0, 1.2, 0]]}},
              Who.person())
    b = Bridge3D(doc, viewport=None)
    yield b
    b.close()


def test_a_ring_drag_keys_the_turn_at_the_playhead_in_one_undo_step(bridge):
    doc, bone = bridge.doc, "strap_bone2"
    bridge.setFrame(10)                                       # 1 s
    it, t, scene = doc.item(bone), bridge.time, bridge.scene()
    v = {k: float(it.get(k, 0.0)) for k in ("x", "y", "z", "rx", "ry", "rz")}
    rest = dict(v)
    pw, origin, turn = gizmo_bone.frame(doc, it, v, scene, bridge.frame, t)
    chain = skin.bones_of(doc.item("strap"))
    head = skin.segment(skin.transforms(chain, t, [])[1], chain[1][0])[:3]
    world = through.find_item(scene, "strap", bridge.frame)[0]
    assert origin == pytest.approx(aim.point(world, head))     # the rings stand on the bone's head as posed

    view = G.View([0.0, 0.6, 3.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0], 0.4, 800, 600)   # looking down -Z
    c = {"v": v, "view": view, "origin": origin, "axes": G.columns(pw[0]), "turn": turn, "px": 1.0}
    o = view.project(origin)
    g = {"handle": "turn2", "kind": "turn", "start": [o[0] + 60, o[1]], "ctx": c, "line": None}
    n = len(doc.history.changes)
    drag = Drag(doc, Who.person(), "Turn Bone 2")
    moved = set()
    for k in range(1, 9):                                     # a quarter turn round the head, in 8 moves
        a = math.pi / 2 * k / 8
        out, _ = item_drag(g, c, [o[0] + 60 * math.cos(a), o[1] - 60 * math.sin(a)], True, lambda *_: [])
        moved |= {f for f in out if abs(out[f] - v[f]) > 1e-9}
        drag.preview(gizmo_bone.calls(bone, {f: out[f] for f in moved}, t))
    drag.end()

    assert len(doc.history.changes) == n + 1                  # one drag, one undo step
    after = doc.item(bone)
    assert {f: after[f] for f in rest} == rest                # the rest (still Turn, head) never moves
    assert moved and all([k["t"] for k in keys_of(after, f)] == [t] for f in moved)
    assert abs(after.get("rz", 0.0) - keys_of(after, "rz")[0]["v"]) == pytest.approx(90.0, abs=0.5)   # Z ring: a quarter turn
    doc.undo(Who.person())
    assert not doc.item(bone).get("keys")
