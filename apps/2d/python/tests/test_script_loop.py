"""The edit-and-re-run loop: a re-run under the same name replaces what the script made (no duplicates, nothing stale) and
keeps a person's hand edit; run_script `look` returns one contact sheet and the film's faults; an export that waits in
its own call (wait_s) fails loudly when its job fails."""
import sys

import pytest
from rostrum_core import Who
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Runtime
from rostrum_core.mcp.context import ToolContext

from rostrum2d import settings
from rostrum2d.mcp import app_tools, export_wait, make_app

AGENT, SAM = Who.agent("tester"), Who.person("sam")
needs_engine = pytest.mark.skipif(settings.engine_missing_reason() is not None or sys.platform != "win32",
                                  reason=settings.engine_missing_reason() or "the engine's pixels are Windows only")
FIRST = '''comp("main", width=640, height=360, fps=30, duration=4)
a = shape("a", shape="rect", x=100, y=100, w=50, h=50)
a.key("x", {0: 100, 2: 300})
shape("b", shape="rect", x=200, y=200, w=50, h=50)
shape("c", shape="ellipse", x=300, y=200, w=40, h=40)
'''
EDITED = '''comp("main", width=640, height=360, fps=30, duration=4)
shape("a", shape="rect", x=120, y=100, w=50, h=50)
shape("b", shape="rect", x=200, y=200, w=50, h=50)
shape("d", shape="rect", x=400, y=200, w=30, h=30)
'''


def _layers(rt):
    doc = next(iter(rt.app.documents.values()))
    return doc, {l["id"]: l for l in doc.data["comps"][0]["layers"]}, [l["id"] for l in doc.data["comps"][0]["layers"]]


def test_a_rerun_replaces_cleanly_and_keeps_a_hand_edit(tmp_path):
    rt = Runtime(make_app(str(tmp_path), ["demo"]), app_tools())
    assert rt.call("run_script", {"source": FIRST, "name": "film.py"}, AGENT)[0]["ok"]
    doc, _, _ = _layers(rt)
    doc.apply([{"op": "shape.set", "target": "b", "args": {"x": 500}}], SAM)          # a person moves b by hand
    reply, _ = rt.call("run_script", {"source": EDITED, "name": "film.py"}, AGENT)
    assert reply["ok"], reply["summary"]
    _, by_id, ids = _layers(rt)
    assert len(ids) == len(set(ids)) and sum(1 for l in by_id.values() if l["type"] == "camera") == 1
    assert "c" not in by_id and "d" in by_id                    # removed item gone, new one there
    assert by_id["a"]["x"] == 120 and not [k for k in by_id["a"].get("keys", []) if k.get("prop") == "x"]   # the removed keys are gone
    assert by_id["b"]["x"] == 500                               # the hand edit survives


def test_a_failed_look_is_said_and_the_merge_stands(tmp_path, monkeypatch):
    def no_pictures(*a, **k):
        raise RostrumError(codes.RENDER_FAILED, "test", "the pictures", "could not be drawn")
    monkeypatch.setattr("rostrum2d.mcp.script_look.render.small_stills", no_pictures)
    rt = Runtime(make_app(str(tmp_path), ["demo"]), app_tools())
    reply, _ = rt.call("run_script", {"source": FIRST, "name": "film.py", "look": [99]}, AGENT)
    assert reply["ok"] and "Look FAILED" in reply["summary"] and "failed" in reply["data"]["look"]
    assert any("past the end" in w for w in reply["warnings"]) and "c" in _layers(rt)[1]


@needs_engine
def test_look_returns_one_sheet_and_the_faults(tmp_path):
    rt = Runtime(make_app(str(tmp_path), ["demo"]), app_tools())
    reply, images = rt.call("run_script", {"source": FIRST, "name": "film.py", "look": [0.5, 1.5, 3]}, AGENT)
    assert reply["ok"], reply["summary"]
    look = reply["data"]["look"]
    assert look["times"] == [0.5, 1.5, 3.0] and len(images) == 1 and look["sheet"] in reply["files"]
    assert isinstance(look["faults"], list) and all("text" in f and "start" in f for f in look["faults"])
    assert "Look at main" in reply["summary"]


def test_an_export_that_waits_fails_loudly(tmp_path):
    rt = Runtime(make_app(str(tmp_path), ["demo"]), app_tools())
    ctx = ToolContext(rt.app, AGENT, "g", rt.jobs, "render_video")

    def broken(job):
        raise RostrumError(codes.RENDER_FAILED, "render_video", "frame 3", "could not be drawn")
    run = export_wait._waiting(lambda c, a: c.job("render_video main 0-4s", broken))
    with pytest.raises(RostrumError, match="failed"):
        run(ctx, {"wait_s": 5})
