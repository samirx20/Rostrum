"""look_frame `view` (look from anywhere) must never move the shot camera or change the document, and look_motion `path`
must put a part where the shot camera sees it: agents judge a move by these numbers. A stand-in engine, no rendering."""
import copy
import math
import types

from PIL import Image

from rostrum_core import Document, Who
from rostrum_core.mcp import App, Runtime

from rostrum3d import KIND, run_source
from rostrum3d.mcp import draw, look, motion_look

AGENT = Who.agent("tester")
SRC = '''
camera("cam", z=3)
mesh("ball", shape="sphere", radius=0.05).key("x", {0: -0.6, 1: 0.6}, ease="linear")
shot("hero", camera="cam", fps=24, start=0, end=24)
'''


class Engine:
    """Draws nothing: keeps the scene and camera each render was asked with, writes a grey PNG."""

    def __init__(self):
        self.asked = []

    def ensure_scene(self, scene):
        self.scene = scene

    def render(self, progress=None, **req):
        self.asked.append((self.scene, req["camera"]))
        Image.new("RGB", (req["width"], req["height"]), (90, 90, 90)).save(req["png"])
        return {"ok": True, "frames": [{"ms": 1}]}

    def take_notices(self):
        return []


def _runtime(tmp_path, monkeypatch, tools):
    monkeypatch.setattr(look, "look_path", lambda stem, ext="png", project=None: tmp_path / f"{stem}.{ext}")
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    app = App("rostrum-3d", {"scene": doc}, folder=str(tmp_path))
    app.state = types.SimpleNamespace(engine=Engine())
    return doc, app, Runtime(app, tools)


def test_a_view_looks_from_elsewhere_and_leaves_the_document_and_the_shot_camera_as_they_were(tmp_path, monkeypatch):
    doc, app, rt = _runtime(tmp_path, monkeypatch, look.tools)
    before = copy.deepcopy(doc.data)
    reply, _ = rt.call("look_frame", {"frame": 12, "view": {"around": "ball", "turn_deg": 90}}, AGENT)
    assert reply["ok"], reply
    scene, camera = app.state.engine.asked[-1]
    out = reply["data"]["result"]
    assert camera == "rostrum_look_view" and out["camera"] == "rostrum_look_view"
    eye = out["view"]["eye"]                               # walked a quarter round the ball (resting at 0, 0.05, 0 at 0.5 s), 3 m out, to the camera's right
    assert math.dist(eye, [3, 0, 0]) < 1e-3 and out["view"]["target"] == [0.0, 0.05, 0.0], out
    assert doc.data == before and "unchanged" in reply["summary"]
    shot_scene = draw.scene_of(doc, "hero")                # the document's own compiled scene has no view camera
    assert not any(n["id"] == "rostrum_look_view" for n in shot_scene["items"])
    assert any(n["id"] == "rostrum_look_view" for n in scene["items"])
    bad, _ = rt.call("look_frame", {"frame": 0, "view": {"from": [0, 1, 2]}}, AGENT)
    assert not bad["ok"] and "needs \"to\"" in bad["summary"]


def test_a_paths_numbers_are_where_the_shot_camera_sees_the_item():
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    rt = Runtime(App("rostrum-3d", {"scene": doc}), motion_look.tools)
    reply = rt.call("look_motion", {"path": "ball", "from_s": 0, "to_s": 1, "step_s": 0.25, "picture": False}, AGENT)[0]
    assert reply["ok"], reply
    d = reply["data"]
    cam = next(i for i in doc.data["items"] if i["id"] == "cam")
    from rostrum3d.fields import FIELDS
    lens = {p.name: cam.get(p.name, p.default) for p in FIELDS["camera"] if p.name in ("sensorWidth", "focalLength")}
    tan_w = lens["sensorWidth"] / (2 * lens["focalLength"])
    want = [0.5 + (-0.6 + 1.2 * t) / (3 * tan_w) / 2 for t in (0, 0.25, 0.5, 0.75, 1)]
    y = 0.5 - 0.05 / (3 * tan_w * 9 / 16) / 2               # the sphere rests on the ground: its middle 0.05 m up
    assert [r["t"] for r in d["samples"]] == [0, 0.25, 0.5, 0.75, 1]
    assert all(abs(r["x"] - x) < 1e-3 and abs(r["y"] - y) < 1e-3 for r, x in zip(d["samples"], want)), d["samples"]
    travel = (want[-1] - want[0]) * 16 / 9                  # in picture heights (a 16:9 shot)
    assert abs(d["travel"] - travel) < 2e-3 and abs(d["peak_speed"] - travel) < 2e-3, d
    assert "travels" in reply["summary"] and "Renderer: none" in reply["summary"]
    missing = rt.call("look_motion", {"path": "ball.hand.L", "picture": False}, AGENT)[0]
    assert not missing["ok"] and "no joint" in missing["summary"]
