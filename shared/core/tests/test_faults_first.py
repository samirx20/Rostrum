"""Agents rely on faults first: a checked reply opens NOT DONE with each fault (or DONE), a job's faults survive the wait,
and a delivery refuses open faults (the file is not left under the asked-for name) unless `keep` explains each one."""
import sys
from pathlib import Path

from rostrum_core import Who
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.faults import KEEP, deliver, fault
from rostrum_core.mcp.server import Runtime

LOUD = fault("loudness", "-16.9 LUFS, the target is -14", "raise maxLimit to 6 dB", "whole song")


def _rt(tmp: Path):
    sys.path.insert(0, str(Path(__file__).parents[2] / "mcp" / "demo"))
    import toy_server
    out = tmp / "mix.wav"

    def work(job, keep):
        out.write_bytes(b"RIFF")
        found = [dict(LOUD)]
        deliver(found, keep, "render_mix", out)
        return Reply("made", files=[out], faults=found)

    tools = Tools()
    tools.add("render_mix", lambda ctx, a: Reply("queued", ctx.jobs.submit("mix", lambda j: work(j, a.get("keep"))).state()),
              {"properties": dict(KEEP)}, "Renders the mix.")
    tools.add("look_thing", lambda ctx, a: Reply("Looked.", faults=[] if a.get("clean") else [dict(LOUD)]),
              {"properties": {"clean": {"type": "boolean"}}}, "Looks.")
    rt = Runtime(toy_server.make_app(), tools)
    rt.jobs._shared = False
    return rt, out


def test_a_checked_reply_opens_with_its_faults_or_done(tmp_path):
    rt, _ = _rt(tmp_path)
    bad = rt.call("look_thing", {}, Who.agent("t"))[0]
    assert bad["summary"].startswith("NOT DONE: 1 fault. [loudness] -16.9 LUFS") and "fix: raise maxLimit" in bad["summary"]
    assert bad["done"] is False and bad["faults"][0]["id"] == "loudness"
    good = rt.call("look_thing", {"clean": True}, Who.agent("t"))[0]
    assert good["summary"].startswith("DONE:") and good["done"] is True


def test_delivery_refuses_open_faults_and_passes_when_each_is_explained(tmp_path):
    rt, out = _rt(tmp_path)
    refused = rt.call("render_mix", {"wait": 10}, Who.agent("t"))[0]
    assert not refused["ok"] and "NOT DONE" in refused["summary"] and "keep" in refused["summary"]
    assert not out.exists() and (tmp_path / "mix.NOT-DONE.wav").exists()
    kept = rt.call("render_mix", {"wait": 10, "keep": {"loudness": "the client asked for -17 for this cut"}}, Who.agent("t"))[0]
    assert kept["ok"] and out.exists() and kept["summary"].startswith("DONE:") and "Kept on purpose: loudness" in kept["summary"]
