"""What agents rely on for the world: look_frame {what: "in_frame"} says what is in the frame (and when, over a span), look_at reads world px,
and an area picture is the size of the layers it was asked for."""
import sys

import pytest
from rostrum_core import Who
from rostrum_core.mcp import Runtime

from rostrum2d import settings
from rostrum2d.mcp import app_tools, make_app

SCRIPT = '''
comp("main", width=1280, height=720, fps=30, duration=4)
shape("near", shape="rect", x=700, y=470, w=200, h=160)
shape("far", shape="rect", x=3000, y=430, w=200, h=200)
shape("edge", shape="rect", x=1280, y=100, w=200, h=100)
shape("ghost", shape="rect", x=500, y=300, w=100, h=100, opacity=0)
frame().key("x", {0: 640, 3: 2800})
'''
AGENT = Who.agent("tester")
needs_engine = pytest.mark.skipif(settings.engine_missing_reason() is not None or sys.platform != "win32",
                                  reason=settings.engine_missing_reason() or "the engine's pixels are Windows only")


def start(tmp_path):
    rt = Runtime(make_app(str(tmp_path), ["demo"]), app_tools())
    rt.call("run_script", {"source": SCRIPT, "name": "s.py"}, AGENT)
    return rt


def test_in_frame_names_what_is_in_partly_in_out_and_hidden(tmp_path):
    rt = start(tmp_path)
    reply, _ = rt.call("look_frame", {"what": "in_frame", "time": 0}, AGENT)
    rows = {r["id"]: r for r in reply["data"]["layers"]}
    assert (rows["near"]["state"], rows["far"]["state"], rows["edge"]["state"]) == ("in", "out", "partly") and rows["edge"]["share"] == 50
    assert not rows["ghost"]["showing"] and "opacity 0" in rows["ghost"]["why_not_showing"]
    reply, _ = rt.call("look_frame", {"what": "in_frame", "from": 0, "to": 3.9}, AGENT)
    spans = {r["id"]: r for r in reply["data"]["layers"]}
    assert spans["near"]["leaves"] and not spans["near"]["always"]            # the frame pans away from it
    assert spans["far"]["enters"] and spans["far"]["spans"][-1]["to"] == 3.9   # and arrives at the far one


def test_look_at_reads_world_px(tmp_path):
    rt = start(tmp_path)
    reply, _ = rt.call("look_at", {"x": 3000, "y": 430, "time": 3, "space": "world"}, AGENT)
    assert [r["id"] for r in reply["data"]["layers"]] == ["far"] and reply["data"]["inside_frame"]
    reply, _ = rt.call("look_at", {"x": 3000, "y": 430, "time": 0, "space": "world"}, AGENT)
    assert not reply["data"]["inside_frame"]


def test_an_area_export_needs_what_it_is_for(tmp_path):
    rt = start(tmp_path)
    reply, _ = rt.call("render_export", {"format": "png", "time": 0, "area": "items"}, AGENT)
    assert not reply["ok"] and "layers to export" in str(reply)
    reply, _ = rt.call("render_export", {"format": "mp4", "area": "world"}, AGENT)
    assert not reply["ok"] and "pictures (png) only" in str(reply)


@needs_engine
def test_an_items_picture_is_the_size_of_their_box(tmp_path):
    from PIL import Image
    rt = start(tmp_path)
    reply, _ = rt.call("render_export", {"format": "png", "time": 3, "area": "items", "ids": ["near", "far"], "scale": 0.5,
                                         "path": str(tmp_path / "pic")}, AGENT)
    done, _ = rt.call("inspect_job", {"job_id": reply["data"]["job_id"], "wait_s": 25}, AGENT)
    assert done["data"]["status"] == "done", done
    with Image.open(done["data"]["result"]["files"][0]) as im:
        assert abs(im.size[0] - 1250) <= 1 and abs(im.size[1] - 110) <= 1      # x 600–3100, y 330–550, at half scale
