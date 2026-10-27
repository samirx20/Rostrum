"""A material's block view (brief 23b) would break silently: each request from the kit's view is one operation, one
undo step (add, add from a dropped wire = add + wire, wire, move, remove), and a block added with no point chosen
lands left of Surface, never on it; a block's own setting dragged is written
once, at the release; the view is told the blocks again only when the graph changed (a frame or a selection change
leaves its data alone, so nothing resets under a drag); Esc closes it. No viewport or engine."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d import graph as G  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d import esc3d  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402

SRC = '''
cam = camera("cam", z=3)
shell = material("shell", baseColor="#c8553d")
mesh("case", shape="box", material=shell)
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


def graph(b):
    return G.graph_of(b.doc.item("shell"))


def steps(b):
    return len(b.doc.history.changes)


def test_requests_are_one_operation_each(bridge):
    b, bk = bridge, bridge.blocks
    b.select("case")
    assert bk.target == "shell"
    bk.edit(bk.target)
    assert bk.open and bk.selected == "surface" and [x["id"] for x in bk.blocks] == ["surface"]
    assert {r["id"] for r in bk.rows.rows if r.get("row") == "param"} >= {"baseColor", "roughness"}

    n = steps(b)
    bk.add("noise", 0, 0, "", False)                    # + Add block: left of Surface, level with it
    assert [x["type"] for x in graph(b)["blocks"]] == ["noise"] and steps(b) == n + 1
    nid = graph(b)["blocks"][0]["id"]
    surf = graph(b)["surface"]
    assert graph(b)["blocks"][0]["x"] + 180 < surf.get("x", 0) and graph(b)["blocks"][0]["y"] == surf.get("y", 0)
    assert bk.selected == nid and any(r["id"] == "scale" for r in bk.rows.rows if r.get("row") == "param")

    bk.wire(f"{nid}.value", "surface.roughness")
    assert {"from": f"{nid}.value", "to": "surface.roughness"} in graph(b)["wires"] and steps(b) == n + 2
    bk.pick("surface")
    rough = next(r for r in bk.rows.rows if r.get("id") == "roughness")
    assert (rough.get("note") or {}).get("text") == "Set by a wire"

    bk.add("mix", -300, 200, f"{nid}.colour", True)          # dropped from a wire: the block and its wire, one step
    mix = next(x for x in graph(b)["blocks"] if x["type"] == "mix")
    assert any(w["from"] == f"{nid}.colour" and w["to"].startswith(mix["id"] + ".") for w in graph(b)["wires"])
    assert steps(b) == n + 3

    bk.move(nid, -400, 60)
    assert next(x for x in graph(b)["blocks"] if x["id"] == nid)["x"] == -400 and steps(b) == n + 4
    bk.unwire("surface.roughness")
    assert all(w["to"] != "surface.roughness" for w in graph(b)["wires"]) and steps(b) == n + 5
    bk.remove([mix["id"], "surface"])                   # Surface is the material: it stays
    assert [x["id"] for x in graph(b)["blocks"]] == [nid] and steps(b) == n + 6


def test_a_block_setting_drag_is_written_once_at_the_release(bridge):
    b, bk = bridge, bridge.blocks
    bk.edit("shell")
    bk.add("noise", 0, 0, "", True)
    nid = bk.selected
    n = steps(b)
    bk.beginScrub("scale")
    for v in (6.0, 7.0, 8.0):
        bk.scrub("scale", v)
    assert steps(b) == n                                # the document stands still during the drag
    bk.endScrub()
    assert steps(b) == n + 1 and G.values(b.doc.item("shell"), graph(b)["blocks"][0])["scale"] == 8.0
    assert next(x for x in bk.blocks if x["id"] == nid)["summary"].startswith("Scale 8")


def test_the_view_data_stays_put_until_the_graph_changes(bridge):
    b, bk = bridge, bridge.blocks
    bk.edit("shell")
    told = []
    bk.changed.connect(lambda: told.append(1))
    b.setFrame(1)
    b.select("case")
    b.outlineChanged.emit()
    assert told == []
    bk.add("noise", 0, 0, "", True)
    assert told


def test_esc_closes_the_blocks(bridge):
    b, bk = bridge, bridge.blocks
    b.select("case")
    bk.edit("shell")
    assert esc3d.step(b) == "blocks" and not bk.open and b.selected == "case"
