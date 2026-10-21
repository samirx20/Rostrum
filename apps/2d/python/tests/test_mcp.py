"""What agents rely on from rostrum-2d: a script re-run keeps a person's edit, changes reach the file at once,
and look_motion reports the facts it promises (read from keys, nothing rendered)."""
from rostrum_core import Document, Who
from rostrum_core.mcp import Runtime

from rostrum2d import KIND
from rostrum2d.mcp import app_tools, make_app

SCRIPT = '''
comp("main", width=1280, height=720, fps=30, duration=3)
a = text("a", body="A", x=200, y=300)
a.key("opacity", {0.0: 0, 1.0: 1})
b = text("b", body="B", x=400, y=300)
b.key("opacity", {0.5: 0, 1.5: 1})
b.key("scale", {0.5: 1.0})
'''
AGENT = Who.agent("tester")


def start(tmp_path):
    app = make_app(str(tmp_path), ["demo"])
    return app, Runtime(app, app_tools())


def test_rerun_keeps_a_persons_edit_and_it_is_already_saved(tmp_path):
    app, rt = start(tmp_path)
    reply, _ = rt.call("run_script", {"source": SCRIPT, "name": "s.py"}, AGENT)
    assert reply["ok"], reply
    doc = app.documents["demo"]
    doc.apply({"op": "text.set", "target": ["a"], "args": {"x": 777}}, Who.person("sam"))     # a person drags it
    reply, _ = rt.call("run_script", {"source": SCRIPT.replace("x=200", "x=250"), "name": "s.py"}, AGENT)
    assert reply["ok"] and doc.item("a")["x"] == 777
    assert [h["key"] for h in reply["data"]["held"]] == ["a.x"]
    assert Document.open(str(tmp_path), "demo", KIND).item("a")["x"] == 777              # the 2D screen sees the same file


def test_look_motion_reports_overlap_and_a_key_that_does_nothing(tmp_path):
    _, rt = start(tmp_path)
    rt.call("run_script", {"source": SCRIPT, "name": "s.py"}, AGENT)
    reply, _ = rt.call("look_motion", {}, AGENT)
    kinds = {f["kind"] for f in reply["data"]["findings"]}
    assert reply["ok"] and {"entrances_overlap", "key_does_nothing", "nothing_moves"} <= kinds
    overlap = next(f for f in reply["data"]["findings"] if f["kind"] == "entrances_overlap")
    assert overlap["layers"] == ["a", "b"] and overlap["overlap_s"] == 0.5
