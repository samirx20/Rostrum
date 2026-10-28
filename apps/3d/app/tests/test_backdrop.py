"""The new scene's Ground is a backdrop (start_scene.py): a right-click on it is a right-click on empty space (nothing
selected, empty space's menu), a left click still selects it, and selected it is never offered Turn into clay or Make
copies (Simulate stays: Stays still on the floor). No viewport or engine: the viewport's pick answer runs on a stand-in."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum3d.start_scene import SOURCE  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402
from screen3d.viewport import Viewport  # noqa: E402


@pytest.fixture
def bridge():
    QGuiApplication.instance() or QGuiApplication([])
    doc = Document.new(KIND)
    doc.run_script("start.py", run_source(SOURCE + 'mesh("ball", shape="sphere", radius=0.1, y=0.1)\n', "start.py"))
    b = Bridge3D(doc, viewport=None)
    yield b
    b.close()


def labels(b):
    return [e["label"] for e in b.actions.menu()]


def test_the_ground_selected_offers_no_clay_or_copies_but_simulate(bridge):
    bridge.select("ground")
    menu = labels(bridge)
    assert "Turn into clay" not in menu and "Make copies" not in menu and "Simulate" in menu
    bridge.select("ball")
    assert {"Turn into clay", "Make copies"} <= set(labels(bridge))


def _picker(bridge):
    """The viewport's pick answer (Viewport._on_picked) on a stand-in with just what it reads."""
    said = []
    vp = SimpleNamespace(bridge=bridge, _drop="", _right_pick=False, _guard=lambda f: f(),
                         copies=SimpleNamespace(picked=lambda item, reply: False),
                         picked=SimpleNamespace(emit=said.append))
    vp._backdrop = lambda item: Viewport._backdrop(vp, item)
    return vp, said


def test_a_right_click_on_the_ground_is_a_right_click_on_empty_space(bridge):
    vp, said = _picker(bridge)
    vp._right_pick = True
    Viewport._on_picked(vp, "ground")
    assert said == [""] and bridge.selected == ""
    vp._right_pick = True
    Viewport._on_picked(vp, "ball")                              # anything else: as before
    assert said[-1] == "ball" and bridge.selected == "ball"
    Viewport._on_picked(vp, "ground")                            # a left click selects the ground
    assert said[-1] == "ground" and bridge.selected == "ground"
