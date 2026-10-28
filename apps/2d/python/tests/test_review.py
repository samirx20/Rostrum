"""look_review names a film's weakest moments with times: a blank stretch and framing that never changes, on a tiny scene."""
from rostrum_core import Who

from rostrum2d.mcp import make_app
from rostrum2d.mcp.server import make_runtime

AGENT = Who.agent("tester")
SCENE = ('comp("main", width=320, height=180, fps=10, duration=12, background="#101010")\n'
         'shape("a", x=40, y=40, w=240, h=100, fill="#e0e0e0", start=0, end=4)\n'
         'shape("b", x=40, y=40, w=240, h=100, fill="#e0e0e0", start=8, end=12)')


def _done(rt, reply):
    job = (reply.get("data") or {}).get("job_id")
    while job and (reply.get("data") or {}).get("status") not in ("done", "failed"):
        reply, _ = rt.call("inspect_job", {"job_id": job, "wait_s": 25}, AGENT)
    return reply


def test_review_names_the_empty_stretch_and_the_held_framing(tmp_path):
    rt = make_runtime(make_app(str(tmp_path), ["demo"]))
    rt.call("run_script", {"source": SCENE, "name": "s.py"}, AGENT)
    reply = _done(rt, rt.call("look_frame", {"what": "review"}, AGENT)[0])
    assert "data" in reply, reply
    data = reply["data"].get("result", reply["data"])
    kinds = {m["kind"]: m for m in data["moments"]}
    assert kinds["empty"]["start"] == 4 and kinds["empty"]["end"] == 8, data["moments"]
    assert (kinds["framing_held"]["start"], kinds["framing_held"]["end"]) == (0, 12)
    assert data["moments"][0]["kind"] == "empty"            # a blank in the middle is named first
    assert "4–8 s: near-empty" in reply["summary"] and "framing never changes" in reply["summary"]


def test_folded_names_answer_with_the_tool_and_what_to_pass(tmp_path):
    """look_review, inspect_diagnose, inspect_layout and render_video are choices of look_frame / render_export now; for
    one version the old name is an error naming the new tool and its `what` (CONVENTIONS § 2), never a silent call."""
    rt = make_runtime(make_app(str(tmp_path), ["demo"]))
    for old, new, what in [("look_review", "look_frame", "review"), ("inspect_diagnose", "look_frame", "diagnose"),
                           ("inspect_layout", "look_frame", "layout"), ("render_video", "render_export", "video")]:
        reply, _ = rt.call(old, {}, AGENT)
        assert reply["ok"] is False and reply["error"]["code"] == "UNKNOWN_TOOL", reply
        assert f'Use {new} with what: "{what}"' in reply["summary"], reply["summary"]
    rt.call("run_script", {"source": SCENE, "name": "s.py"}, AGENT)
    found = rt.call("look_frame", {"what": "diagnose"}, AGENT)[0]
    assert found["ok"] is True, found
