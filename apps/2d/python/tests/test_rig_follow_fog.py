"""rig.follow bakes lagging rotation keys on the bones below the target; frame.fog lays fog sheets whose opacities add
up to the asked fog on each layer, and refuses a stack that contradicts depth. Agents rely on both; they break silently."""
import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND, run_source
from rostrum2d.ops_fog import sheets

SAM = Who.person("sam")
SRC = '''
comp("c", duration=3)
with rig("r", w=600, h=800):
    up = bone("up", x=300, y=300, angle=90, length=100)
    lo = bone("lo", parent=up, length=100)
    up.key("rotation", {0: 0, 0.5: 40, 1: 0})
'''


def test_follow_lags_the_child_and_leaves_the_target():
    d = Document.new(KIND)
    d.run_script("r.py", run_source(SRC, "r.py"))
    d.apply({"op": "rig.follow", "target": "up", "args": {"start": 0, "end": 1, "lag": 0.1}}, SAM)
    keys = [(k["t"], k["v"]) for k in d.item("lo")["keys"] if k["prop"] == "rotation"]
    assert len(keys) > 4 and any(v < -1 for _, v in keys) and any(v > 1 for _, v in keys)   # trails, then swings past
    assert abs(keys[-1][1]) < 0.5                                                           # settled
    assert len([k for k in d.item("up")["keys"] if k["prop"] == "rotation"]) == 3          # target untouched


def test_fog_sheets_add_up_to_the_asked_fog():
    planned, clamped = sheets([("far", 3.0), ("mid", 1.5), ("near", 0.0)], 0.0, 3.0, 0.6, 1.0)
    over = dict(planned)
    assert not clamped and over["near"] == 0.0 and over["mid"] == pytest.approx(0.3)
    assert 1 - (1 - over["far"]) * (1 - over["mid"]) == pytest.approx(0.6, abs=1e-3)      # the far layer sits under both sheets
    _, clamped = sheets([("a", 0.0), ("b", 3.0)], 0.0, 3.0, 0.6, 1.0)           # a nearer layer BELOW a farther one
    assert clamped == ["a"]
