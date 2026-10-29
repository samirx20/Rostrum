"""look_motion `path` takes the names the pose tools take (the guides' "buddy.hand.R" on a figure whose arm ends at
forearm.R), and an engine ended by our own stop (run_stop) is not reported as a crash. No engine, no rendering."""
import subprocess
import sys
import types

import pytest

from rostrum3d import view_look
from rostrum3d.engine import Engine

IDENT = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def _fr():
    arm = {"id": "b_arm_R", "type": "bone", "joint": "arm.R", "length": 0.3, "bones": [
        {"id": "b_forearm_R", "type": "bone", "joint": "forearm.R", "length": 0.25, "y": 0.3, "bones": [], "keys": []}], "keys": []}
    body = {"id": "b_body", "type": "bone", "joint": "body", "length": 0.5, "bones": [arm], "keys": []}
    return types.SimpleNamespace(items={"buddy": {"id": "buddy", "type": "clay", "bones": [body]}}, fps=24, stack=[],
                                 held=lambda owner, f: f, world=lambda owner, f: (IDENT, [0, 0, 0]))


def test_the_guides_hand_name_finds_the_end_of_a_short_arm_and_the_error_lists_the_names():
    fr = _fr()
    hand, forearm = (view_look.part_point(fr, f"buddy.{j}")(0) for j in ("hand.R", "forearm.R"))
    assert hand == forearm and view_look.part_point(fr, "buddy.right hand")(0) == hand
    with pytest.raises(ValueError) as e:
        view_look.part_point(fr, "buddy.wing.R")
    assert "forearm.R" in str(e.value) and "arm.R" in str(e.value)


def test_an_engine_we_stopped_ourselves_restarts_without_a_crash_notice(tmp_path):
    eng = Engine.__new__(Engine)
    eng.stopped, eng.restarts, eng._notices, eng._ours, eng.pid, eng.log_path = False, 0, [], None, 1, tmp_path / "e.log"
    eng._start = lambda: None
    eng.proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    eng.kill()
    eng._ensure_running()
    assert eng.restarts == 1 and eng.take_notices() == []
    eng.proc = subprocess.Popen([sys.executable, "-c", "raise SystemExit(1)"])
    eng.proc.wait()
    eng._ensure_running()
    assert "stopped (exit 1" in eng.take_notices()[0]
