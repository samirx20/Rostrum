"""Declared beats: one that already happened well before its time is named with both times; one on time is not; the
beats given once are kept and checked again without being repeated."""
from rostrum_core import Who

from rostrum2d.mcp import make_app, review
from rostrum2d.mcp.server import make_runtime

AGENT = Who.agent("tester")
SCENE = ('comp("main", width=320, height=180, fps=10, duration=12, background="#101010")\n'
         'shape("early", x=80, y=50, w=100, h=60, fill="#e0e0e0")\n'
         'shape("late", x=240, y=50, w=100, h=60, fill="#e0e0e0", start=8)\n'
         'shape("slow", x=80, y=130, w=100, h=60, fill="#e0e0e0").key("opacity", {0: 0, 8: 0, 10: 1})')


def _scene(tmp_path):
    app = make_app(str(tmp_path), ["demo"])
    rt = make_runtime(app)
    rt.call("run_script", {"source": SCENE, "name": "s.py"}, AGENT)
    return rt, app.documents["demo"]


def _done(rt, reply):
    job = (reply.get("data") or {}).get("job_id")
    while job and (reply.get("data") or {}).get("status") not in ("done", "failed"):
        reply, _ = rt.call("inspect_job", {"job_id": job, "wait_s": 25}, AGENT)
    return reply


def _said(doc, beats):
    faults, _ = review.doc_faults(doc.data, doc.data["comps"][0], beats, "test")
    return [f["text"] for f in faults if f["kind"].startswith("beat")]


def test_a_beat_that_already_happened_is_named_and_one_on_time_is_not(tmp_path):
    _, doc = _scene(tmp_path)
    said = _said(doc, [{"at": 8, "expect": "early shows"}, {"at": 8, "expect": "late shows"},
                       {"at": 8, "to": 10, "expect": "slow reveals"}, {"at": 4, "to": 6, "expect": "early reveals"}])
    assert said == ["8 s: 'early shows' already happened at 0 s (100 % of early showing); the beat is meant at 8 s",
                    "4–6 s: 'early reveals' already happened at 0 s (early whole, 100 % showing); the beat is meant at 4–6 s"], said


def test_beats_given_once_are_kept_and_a_bad_one_fails_before_any_job(tmp_path):
    rt, doc = _scene(tmp_path)
    bad, _ = rt.call("render_export", {"format": "mp4", "beats": [{"at": 1, "expect": "lamp shows"}]}, AGENT)
    assert bad["ok"] is False and "lamp" in bad["summary"], bad
    assert "No beats declared" in review.after_export(doc.data, doc.data["comps"][0], [], [], beats=None)
    _done(rt, rt.call("look_frame", {"what": "review", "beats": [{"at": 8, "expect": "early shows"}]}, AGENT)[0])
    again = _done(rt, rt.call("look_frame", {"what": "review"}, AGENT)[0])                         # no beats given: the kept ones
    assert "'early shows' already happened at 0 s" in again["summary"], again["summary"]
