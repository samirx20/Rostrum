"""Every key on the Keys sheet (Ctrl+/) does something, and Esc and right-click are one list each: the sheet and the
shortcuts are one key map (keys3d.KEYS3D), right-click is the action hub's menu. No viewport or engine."""
import re
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d import esc3d  # noqa: E402
from screen3d.actions3d import LIST  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402
from screen3d.keys3d import KEYS3D, ROUTES, SKIP, WINDOW  # noqa: E402

QML = Path(__file__).resolve().parents[1] / "qml" / "Main.qml"


def test_every_listed_key_has_something_behind_it():
    behind = set(ROUTES) | set(WINDOW) | set(SKIP) | {LIST.job_of(a) for a in LIST.actions}
    dead = [(e["job"], e["keys"]) for e in KEYS3D.entries() if e["job"] not in behind]
    assert not dead, f"listed on the Keys sheet but nothing runs: {dead}"


def test_routes_name_real_bridge_methods_and_window_jobs_are_answered():
    missing = [(j, r[0]) for j, r in ROUTES.items() if not hasattr(Bridge3D, r[0])]
    assert not missing, f"keys3d.ROUTES names a bridge method that does not exist: {missing}"
    text = QML.read_text(encoding="utf-8")
    block = text[text.index("windowJobs: ({"):text.index("Connections { target: backend.actions; function onWindowJob")]
    unanswered = [j for j in WINDOW if not re.search(rf"\b{j}\s*:", block)]
    assert not unanswered, f"keys3d.WINDOW jobs Main.qml windowJobs does not answer: {unanswered}"


def test_shared_keys_mean_what_they_mean_everywhere():
    """Left / Right nudge, Ctrl+1 is no page, Tab walks the items, V is Select, B is Paint (2D and Sound's meanings)."""
    assert KEYS3D.job_of("Left") == "nudge_left" and KEYS3D.job_of("Right") == "nudge_right"
    assert KEYS3D.job_of("Ctrl+1") == "" and KEYS3D.job_of("Tab") == "next_item"
    assert KEYS3D.job_of("V") == "move_tool" and KEYS3D.job_of("B") == "paint_tool"
    assert KEYS3D.job_of("Q") == "clay_tool"               # Clay (3d-simplicity SPEC; clay_tool_qt.py)


def test_no_hand_bound_key_left_in_the_window():
    """The window binds no key of its own beside the key map (a second Shortcut on a key made Qt run neither)."""
    qml = Path(__file__).resolve().parents[1] / "qml"
    own = [(f.name, m) for f in qml.glob("*.qml") for m in re.findall(r'KeyShortcut \{[^}]*sequence: "([^"]+)"', f.read_text(encoding="utf-8"))]
    assert not own, f"keys bound by hand, outside keys3d.py: {own}"


SRC = '''
cam = camera("cam", z=3)
m = material("red", baseColor="#cc3333")
mesh("box", shape="box", y=0.5, material=m)
mesh("ball", shape="sphere", x=1)
light("lamp", kind="rect", y=2)
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


def test_right_click_is_the_hub_list_eight_at_most_with_the_real_keys(bridge):
    for pick in ([], ["box"], ["cam"], ["lamp"], ["s"], ["box", "ball"]):
        bridge.selectMany(pick) if pick else bridge.select("")
        menu = bridge.actions.menu()
        assert len(menu) <= 8, (pick, menu)      # six, Make copies › (brief 24) and Simulate › (brief 25), one row each
        offered = {e["value"] for e in menu}
        assert offered <= set(bridge.actions.offered) | {e["value"] for e in menu if e["sub"]}, pick
    bridge.select("box")
    keys = {e["value"]: e["keys"] for e in bridge.actions.menu()}
    assert keys["mesh:edit"] == "Enter" and keys["item:duplicate"] == "Ctrl+D" and keys["item:delete"] == "Delete"
    assert keys["material:copy"] == "Ctrl+Alt+C"


def test_copy_then_paste_material_is_one_change(bridge):
    bridge.select("box")
    bridge.actions.choose("material:copy")
    bridge.select("ball")
    n = len(bridge.doc.history.changes)
    bridge.actions.key("paste_style")
    assert bridge.doc.item("ball")["material"] == "red" and len(bridge.doc.history.changes) == n + 1


def test_esc_steps_back_one_thing_at_a_time_in_the_written_order(bridge):
    bridge.select("box")
    bridge.add.arm("mesh:box")
    assert esc3d.step(bridge) == "armed" and bridge.add.armed == "" and bridge.selected == "box"
    assert esc3d.step(bridge) == "selection" and bridge.selected == ""
    assert esc3d.step(bridge) == ""


def test_arrows_nudge_the_selection_one_undo_step_each(bridge):
    bridge.select("box")
    x0, n = bridge.doc.item("box")["x"], len(bridge.doc.history.changes)
    bridge.actions.key("nudge_right")
    bridge.actions.key("nudge_left_big")
    assert bridge.doc.item("box")["x"] == pytest.approx(x0 + 0.01 - 0.1)
    assert len(bridge.doc.history.changes) == n + 2


def test_ctrl_k_offers_jobs_only_when_they_would_change_something(bridge):
    keys = lambda: {c["key"] for c in bridge.extra_commands()}  # noqa: E731
    assert "job:page_build" not in keys() and "job:page_render" in keys()
    bridge.setPage("render")
    assert "job:page_build" in keys() and "job:page_render" not in keys()
    bridge.select("box")
    assert "mesh:edit" in keys() and "job:mesh_faces" not in keys()       # Edit mesh is the action's row; its tools only inside
    bridge.select("")
    assert "mesh:edit" not in keys()
