"""What agents rely on: an engine refusal reaches them as a loud error with the core's own words, and a dead engine is reported
(then started again with the scene sent again), never silent. Uses a stand-in process, no rendering."""
import os
import sys
import types
from pathlib import Path

import pytest

try:
    import rostrum3d.compile                                  # the real one, when it is there
except ImportError:
    stub = types.ModuleType("rostrum3d.compile")
    stub.describe, stub.shot_info = (lambda data, shot: {"shot": shot}), (lambda data, shot: data)
    sys.modules["rostrum3d.compile"] = stub

from rostrum_core import Who
from rostrum_core.mcp import App, Runtime

from rostrum3d.engine import Engine, EngineError
from rostrum3d.mcp import look

FAKE = Path(__file__).with_name("fake_core.py")
INFO = {"id": "hero", "camera": "cam", "fps": 24, "start": 0, "end": 47, "width": 1920, "height": 1080}


class Doc:
    item_id, data, seq, folder = "demo", dict(INFO, shots=[{"id": "hero"}]), 1, None   # no project: looks go to the cache
    history = types.SimpleNamespace(changes=[])


def engine():
    return Engine(sys.executable, dict(os.environ), args=(str(FAKE), "serve"))


def test_refusal_is_loud_and_a_dead_engine_is_reported_then_restarted(tmp_path, monkeypatch):
    monkeypatch.setattr(look, "LOOK_SAMPLES", 1)
    monkeypatch.setattr(look, "look_path", lambda stem, ext="png", project=None: tmp_path / f"{stem}.{ext}")
    monkeypatch.setattr(look.draw, "scene_of", lambda doc, shot: {"shot": shot})
    shot = {"value": dict(INFO)}
    monkeypatch.setattr(look, "doc_and_shot", lambda ctx, args: (Doc, shot["value"]))
    eng = engine()
    app = App("rostrum-3d", {"demo": Doc}, folder=str(tmp_path))
    app.state = types.SimpleNamespace(engine=eng)
    rt = Runtime(app, look.tools)
    try:
        ok, images = rt.call("look_frame", {"frame": 0}, Who.agent("t"))
        assert ok["ok"], ok; assert images and Path(ok["files"][0]).is_file()

        shot["value"] = dict(INFO, camera="nocam")                 # the engine says ok:false
        bad, _ = rt.call("look_frame", {"frame": 0}, Who.agent("t"))
        assert not bad["ok"] and 'no camera "nocam"' in bad["summary"]
        shot["value"] = dict(INFO)

        dead, _ = rt.call("look_frame", {"frame": 7}, Who.agent("t"))   # the process exits mid-request
        assert not dead["ok"] and "ended without a reply" in dead["summary"]

        again, _ = rt.call("look_frame", {"frame": 8}, Who.agent("t"))  # next call: started again, and it says so
        assert again["ok"] and any("started again" in w for w in again["warnings"]), again
    finally:
        eng.close()


def test_missing_engine_says_how_to_build_it(tmp_path):
    with pytest.raises(EngineError, match="not found"):
        Engine(tmp_path / "nope.exe").ensure_scene({})
