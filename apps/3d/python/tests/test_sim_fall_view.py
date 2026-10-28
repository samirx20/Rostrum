"""Seeing the fall (3D gaps round 2): how many of a fall's frames the shot camera shows, and sim.start_in_view putting a
thing's top where asked in the picture. Both would quietly say the wrong thing if the arithmetic slipped. No engine."""
from __future__ import annotations

import array
from pathlib import Path

import pytest
from rostrum_core import Document, Who
from rostrum_core.cache import CACHE

from rostrum3d import KIND, run_source
from rostrum3d.compile import shot_info
from rostrum3d.item_bounds import world_box
from rostrum3d.motion_track import Camera
from rostrum3d.resolve import Frames
from rostrum3d.sim import fall_view, ops as sim_ops
from rostrum3d.sim.inputs import JOLT_VERSION, SIM_VERSION

SAM = Who.person()
SRC = '''
cam = camera("cam", focalLength=40, x=0, y=1.25, z=1.55).aim((0, 0.78, 0))
mesh("table", shape="box", width=1.4, height=0.06, depth=0.9, y=0.72).simulate("still")
mesh("sweet", shape="sphere", radius=0.035, x=-0.2, y=1.6).simulate("falls")
shot("spill", camera=cam, fps=24, start=0, end=1, width=1280, height=720)
'''


class Drop:
    """Answers `simulate`: the sweet falls from y 1.6 to 0.79 over frames 0–15, then rests."""

    def ensure_scene(self, scene):
        pass

    def simulate(self, progress=None, **req):
        frames = range(req["start"], req["end"] + 1)
        data = array.array("f")
        for i, _ in enumerate(frames):
            y = 1.6 - (1.6 - 0.79) * min(i, 15) ** 2 / 225
            data.extend([-0.2, y, 0.0, 0.0, 0.0, 0.0, 1.0])
        Path(req["folder"], "bodies.bin").write_bytes(data.tobytes())
        return {"ok": True, "jolt": JOLT_VERSION, "sim": SIM_VERSION, "frames": [req["start"], req["end"]], "rows": 1,
                "bodies": [{"item": "sweet", "copy": 0, "row": 0}], "atRest": 1, "ms": 1}

    def close(self):
        pass


@pytest.fixture
def doc(tmp_path, monkeypatch):
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    sim_ops.use_engine_factory(Drop)
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    yield d
    CACHE.settle()
    sim_ops.use_engine_factory(None)


def test_classify_counts_on_and_off_screen_frames():
    frames = list(range(12))
    pace = [0.05] * 9 + [0.0] * 2                    # moves frames 1–9, still at 10–11
    seen = ["above"] * 7 + ["part", "in", "in", "in", "in"]
    low = [2.0 - 0.1 * min(i, 9) for i in frames]    # goes down frames 0–9 (lands at 9), still after
    f = fall_view.classify(frames, pace, seen, 24, low)
    assert (f["drop"], f["onScreen"], f["offScreen"], f["enters"], f["where"]) == ([0, 9], 3, 7, 7, "above")
    text, fix = fall_view.line("sweet", "falls", f, 24)
    assert fix and "above the picture" in text and "enters at frame 7" in text and "sim.start_in_view" in text
    rest = fall_view.classify(frames, [0.0005] * 11, ["in"] * 12, 24)
    assert rest["startsAtRest"] and fall_view.line("sheet", "cloth", rest, 24)[1]


def test_a_fall_from_above_the_picture_is_named(doc):
    doc.apply([{"op": "sim.run", "target": ["spill"]}], SAM)
    row = fall_view.views(doc.data, shot_info(doc.data, "spill"), None)[0]
    assert row["item"] == "sweet" and row["offScreen"] > 0 and row["where"] == "above" and row["fix"]
    assert "sweet" in fall_view.fall_note(doc.data, "spill")


def test_start_in_view_puts_its_top_where_asked(doc):
    doc.apply([{"op": "sim.start_in_view", "target": ["sweet"], "args": {"fromTop": 0.2}}], SAM)
    lo, hi = world_box(doc.data, ["sweet"], 0.0)
    cam = Camera(Frames(doc.data, range(0, 1), 24), "cam", 0, 1280, 720)
    _, y = cam.project([(lo[0] + hi[0]) / 2, hi[1], (lo[2] + hi[2]) / 2])
    assert abs(y - 0.2 * 720) < 1.0
    with pytest.raises(Exception, match="inside or under table"):           # that low it would start inside the table
        doc.apply([{"op": "sim.start_in_view", "target": ["sweet"], "args": {"fromTop": 0.9}}], SAM)


def test_a_cut_that_opens_mid_drop_or_after_the_landing_says_so(doc):
    doc.apply([{"op": "sim.run", "target": ["spill"]}], SAM)
    mid = fall_view.fall_note(doc.data, "spill", None, (8, 23))
    assert "starts at 0.3 s" in mid and "mid-drop" in mid and "render_video `start`" in mid
    after = fall_view.fall_note(doc.data, "spill", None, (20, 23))
    assert "already fallen" in after


def test_a_long_still_stretch_and_a_shot_opening_mid_fall_are_named():
    from rostrum3d.sim.cut_note import cut_lines
    frames = list(range(240))
    pace = [0.05] * 10 + [0.0] * 229                 # moves at speed from the first frame, still from frame 11
    low = [2.0 - 0.1 * min(i, 10) for i in frames]
    f = fall_view.classify(frames, pace, ["in"] * 240, 24, low)
    assert f["underway"]
    row = {"item": "sheet", "kind": "cloth", **f}
    text = " ".join(cut_lines([row], 0, 239, 0, 24))
    assert "already moving at the first frame" in text and "the last 9.5 s of this 10.0 s cut don't move" in text
    from_rest = fall_view.classify(frames, [0.01 * (i + 1) for i in range(10)] + [0.0] * 229, ["in"] * 240, 24, low)
    assert not from_rest["underway"]
