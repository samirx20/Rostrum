"""What agents rely on for their time (the 3D benchmark's agents used 2 of 12 minutes): the clock line after a video counts the
look-fix-export passes the time left allows, and render_video's estimate_only and an over-budget render answer at once with
figures and settings (over the budget it renders anyway), never as a job to ask about later."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.errors import RostrumError
from rostrum_core.mcp import Reply, Runtime

from rostrum3d import KIND, run_source
from rostrum3d.mcp import render, session_clock
from rostrum3d.mcp.server import app_tools, make_app

SRC = '''
cam = camera("cam", focalLength=50, z=3).aim((0, 0, 0))
mesh("ball", shape="sphere", radius=0.2)
shot("hero", name="Hero 01", camera=cam, fps=10, start=0, end=1)
'''


def test_passes_left_after_a_video_and_the_clock_line():
    t = [1000.0]
    clock = session_clock.Clock(now=lambda: t[0], budget_min=12)
    clock.begin()
    t[0] += 2 * 60
    clock.noted("inspect_job", {}, Reply("done", {"label": "render_video hero f0-9", "status": "done", "result": {"seconds": 30.0}}))
    line = clock.line()                                           # 10 min left / (30 s export + 150 s pass)
    assert "the last video has not been looked at" in line and "10 min 00 s of your 12 min left" in line
    assert "about 3 more passes of look, fix and export" in line
    clock.noted("look_frame", {"what": "sheet"}, Reply("sheet"))
    assert "has not been looked at" not in clock.line()
    t[0] += 9 * 60
    assert "more pass" not in clock.line()                        # 1 min left: no pass fits
    # a running job or an estimate_only answer is not an export
    fresh = session_clock.Clock(now=lambda: t[0], budget_min=12)
    fresh.noted("inspect_job", {}, Reply("running", {"label": "render_video hero f0-9", "status": "running"}))
    fresh.noted("inspect_job", {}, Reply("done", {"label": "render_video hero f0-9", "status": "done", "result": {"estimate_s": 40.0}}))
    assert not fresh.exported


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    class Engine:
        exe = "x"

        def close(self):
            pass

        def __getattr__(self, name):                 # whatever else make_app hands it to (the mesh and import ops)
            return lambda *a, **k: None

        def take_notices(self):
            return []
    doc = Document.new(KIND, tmp_path, "shot")
    doc.run_script("s.py", run_source(SRC, "s.py"), Who.agent("t"))
    monkeypatch.setattr(render, "check_ffmpeg", lambda where: None)
    return Runtime(make_app(str(tmp_path), documents={"shot": doc}, engine=Engine()), app_tools())


def _measured(seconds):
    return lambda *a, **k: (seconds, {"estimate_s": seconds, "seconds_per_frame": seconds / 10, "how": "measured now on this scene"}, lambda change, v: seconds / 2)


def test_estimate_only_returns_the_figures_even_over_budget(runtime, monkeypatch):
    monkeypatch.setattr(render, "_estimate", _measured(1320.0))
    reply, _ = runtime.call("render_video", {"estimate_only": True, "budget_min": 9}, Who.agent("t"))
    assert reply["ok"], reply
    assert "about 1320 s" in reply["summary"] and "over the 9.0 min budget" in reply["summary"] and "Try one of" in reply["summary"]
    assert reply["data"]["over_budget"] is True and reply["data"]["fits"]


def test_over_budget_renders_anyway_and_says_the_estimate_at_once(runtime, monkeypatch):
    monkeypatch.setattr(render, "_estimate", _measured(1320.0))
    monkeypatch.setattr(render, "video", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("drawing started")))
    reply, _ = runtime.call("render_video", {"budget_min": 9}, Who.agent("t"))
    assert reply["ok"] and "job" in reply["summary"], reply          # never refused: the render is a job like any other
    assert "Rendering anyway" in reply["summary"] and "over the 9.0 min budget" in reply["summary"] and "Try one of" in reply["summary"]
