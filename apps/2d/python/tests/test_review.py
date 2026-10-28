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
    reply = _done(rt, rt.call("look_review", {}, AGENT)[0])
    assert "data" in reply, reply
    data = reply["data"].get("result", reply["data"])
    kinds = {m["kind"]: m for m in data["moments"]}
    assert kinds["empty"]["start"] == 4 and kinds["empty"]["end"] == 8, data["moments"]
    assert (kinds["framing_held"]["start"], kinds["framing_held"]["end"]) == (0, 12)
    assert data["moments"][0]["kind"] == "empty"            # a blank in the middle is named first
    assert "4–8 s: near-empty" in reply["summary"] and "framing never changes" in reply["summary"]
