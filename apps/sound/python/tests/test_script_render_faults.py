"""What agents rely on: the listening check names a silent start and a tempo bent from the brief's, and run_script's
`look` renders after a script that ran, never after one that failed (no engine: render_mix is a stand-in job)."""
import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest
from rostrum_core import Document, RostrumError, codes
from rostrum_core.mcp import Reply
from rostrum_core.mcp.jobs import InProcessJobs

from rostrum_sound import KIND
from rostrum_sound.listen import lead_in, tempo_fit
from rostrum_sound.mcp import script_render
from rostrum_sound.mcp.moments_arg import parse

SR = 48000
Tool = dataclasses.make_dataclass("Tool", ["fn", "schema", "description"])


def tone(silent_s, total_s=2.0):
    t = np.arange(int(total_s * SR)) / SR
    y = 0.3 * np.sin(2 * np.pi * 220 * t) * (t >= silent_s)
    return np.stack([y, y], axis=1).astype(np.float32)


def test_leading_silence_is_found_only_when_the_music_starts_late():
    found = lead_in.faults(tone(1.0), SR)
    assert [f["kind"] for f in found] == ["leading_silence"] and abs(found[0]["measured"]["first_sound_s"] - 1.0) < 0.03
    assert "downbeat(bar(1)" in lead_in.words(found[0])
    assert lead_in.faults(tone(0.0), SR) == []


def test_a_tempo_expect_is_parsed_and_a_bent_tempo_named(tmp_path):
    doc = Document.new(KIND, folder=str(tmp_path), item="cue")
    doc.data["tempo"], doc.data["length"] = 133, 30
    _, _, moments = parse(doc, [{"kind": "tempo", "bpm": 132}], "render_mix")
    assert moments == [{"kind": "tempo", "bpm": 132.0, "start_bpm": 133.0, "held_bpm": pytest.approx(133.0)}]
    found = tempo_fit.faults(moments[0])
    assert found[0]["kind"] == "off_tempo" and "land(bar(n)" in tempo_fit.words(found[0])
    assert tempo_fit.faults({**moments[0], "bpm": 133}) == []
    with pytest.raises(RostrumError):
        parse(doc, [{"kind": "tempo"}], "render_mix")


def runtime(script_fails):
    rendered = []

    def run_script(ctx, args):                              # the shared run_script: the hook runs only after a merge
        if script_fails:
            raise RostrumError(codes.BAD_ARGUMENT, "run_script", "the script", "has a syntax error")
        reply = Reply("Script ran.", {"song": 1})
        return script_render.after_run(ctx, SimpleNamespace(item_id=None), args["look"], reply) if args.get("look") else reply

    def render_mix(ctx, args):
        rendered.append(args)
        job = ctx.jobs.submit("render", lambda job: Reply("Rendered. Weakest moments: 1. stop lands soft.", {"file": "x.wav"}, ["x.wav"]))
        return Reply("job", job.state())
    tools = {"run_script": Tool(run_script, {"properties": {"source": {}}}, "d"),
             "render_mix": Tool(render_mix, {"properties": {"name": {}, "expect": {}, "what": {}}}, "d")}
    rt = SimpleNamespace(tools=SimpleNamespace(get=tools.get, _tools=tools))
    script_render.with_look(rt)
    return tools["run_script"].fn, SimpleNamespace(jobs=InProcessJobs(shared=False), tools=rt.tools), rendered


def test_run_script_look_renders_after_a_script_that_ran_and_never_after_one_that_failed():
    run, ctx, rendered = runtime(script_fails=False)
    out = run(ctx, {"source": "x", "look": {"name": "cue"}})
    assert rendered == [{"name": "cue"}] and out.summary.startswith("Script ran.\nRendered.") and out.data["look"]["result"]["file"] == "x.wav"
    with pytest.raises(RostrumError):                       # render_mix doesn't take it: refused before the script runs
        run(ctx, {"source": "x", "look": {"stem": True}})
    run, ctx, rendered = runtime(script_fails=True)
    with pytest.raises(RostrumError):
        run(ctx, {"source": "x", "look": True})
    assert rendered == []
