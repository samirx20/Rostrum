"""The agent's clock: every reply ends with one line (time, calls, edits since the last look), inspect_project what "session"
says what is unchecked; and measure_text measures without leaving a layer in the picture."""
from rostrum_core import Who
from rostrum_core.mcp import Reply, Runtime, Tools

from rostrum2d import run_source, textsize
from rostrum2d.mcp import app_tools, make_app, session_clock
from rostrum2d.mcp.session_clock import Clock

AGENT = Who.agent("tester")


class Time:
    now = 100.0

    def __call__(self):
        return self.now


def test_the_line_counts_time_calls_and_edits_since_the_last_look():
    t = Time()
    clock = Clock(t, budget_min=15)
    clock.begin()
    t.now += 372
    clock.begin()
    clock.noted("run_script", {}, Reply("x", changed={"seq": 1}))
    clock.noted("run_script", {}, Reply("x", changed={"seq": 2}))
    assert clock.line() == ("Session 6 min 12 s (since your first call this session) · 2 calls · no look at the picture yet"
                            " · 8 min 48 s of your 15 min left (time to look and refine)")
    clock.noted("look_frame", {}, Reply("x", {"result": {"time": 1.0}}))
    clock.noted("run_script", {}, Reply("x", changed={"seq": 3}))
    assert "last look at the picture 1 edit ago" in clock.line()
    assert clock.unlooked(10.0) == [[3.0, 10.0]] and clock.edits_since_look == 1


def test_a_render_is_unlooked_until_its_film_is_looked_at():
    clock = Clock(Time())
    clock.begin()
    clock.noted("render_video", {}, Reply("x", {"job_id": "j1", "label": "render_video main 0-4s"}))
    assert "the export has not been looked at" in clock.line()
    clock.noted("look_frame", {}, Reply("x", {"result": {"video": "a.mp4", "times": [0.0, 1.0]}}))
    assert "export" not in clock.line() and clock.covered == []       # a film's times are not the composition's


def test_every_reply_of_the_server_ends_with_the_line_and_session_lists_what_is_unchecked(tmp_path):
    from rostrum2d.mcp.server import make_runtime
    rt = make_runtime(make_app(str(tmp_path), ["demo"]))
    reply, _ = rt.call("run_script", {"source": 'comp("main", width=320, height=180, fps=30, duration=8)\nshape("a", x=50, y=50, w=20, h=20)', "name": "s.py"}, AGENT)
    assert reply["ok"] and reply["summary"].splitlines()[-1].startswith("Session ") and "no look at the picture yet" in reply["summary"]
    reply, _ = rt.call("inspect_project", {"what": "session"}, AGENT)
    assert "times never looked at: 0–8 s" in reply["summary"] and reply["data"]["edits_since_look"] == 1


def test_measure_text_leaves_no_layer_and_matches_a_real_texts_measure():
    class Engine:
        def measure(self, items):
            return {i["id"]: (10.0 * len(i["body"]), i["size"]) for i in items}
    textsize._sizes.clear()
    with textsize.use(Engine()):
        tree = run_source('comp("main")\nw, h = measure_text("Alpha", size=80)\nt = text("real", body="Alpha", size=80)\n'
                          'assert (w, h) == t.measure()\nshape("w", w=w, h=h)', "m.py")
    ids = [layer["id"] for comp in tree["comps"] for layer in comp["layers"]]
    assert ids == ["frame", "real", "w"] and "measure_text" not in ids
