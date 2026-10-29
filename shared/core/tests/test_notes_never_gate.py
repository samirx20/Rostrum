"""Rostrum never blocks an agent's work (Sam, 2026-10-29): a render writes the file it was asked for under its own name,
checks run only when the call asks (`notes: true`), and their notes close the reply instead of judging it."""
import sys
from pathlib import Path

from rostrum_core import Who
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.faults import NOTES, asked, note
from rostrum_core.mcp.server import Runtime

LOUD = note("loudness", "-16.9 LUFS, the master's target is -14", "whole song")


def _rt(tmp: Path):
    sys.path.insert(0, str(Path(__file__).parents[2] / "mcp" / "demo"))
    import toy_server
    out = tmp / "mix.wav"

    def work(job, args):
        out.write_bytes(b"RIFF")
        return Reply("made", files=[out], faults=[dict(LOUD)] if asked(args) else None)

    tools = Tools()
    tools.add("render_mix", lambda ctx, a: Reply("queued", ctx.jobs.submit("mix", lambda j: work(j, a)).state()),
              {"properties": dict(NOTES)}, "Renders the mix.")
    rt = Runtime(toy_server.make_app(), tools)
    rt.jobs._shared = False
    return rt, out


def test_a_render_ships_under_its_name_and_says_nothing_unasked(tmp_path):
    rt, out = _rt(tmp_path)
    r = rt.call("render_mix", {"wait": 10}, Who.agent("t"))[0]
    assert r["ok"] and out.exists() and not list(tmp_path.glob("*NOT-DONE*"))
    assert "notes" not in r and "NOT DONE" not in r["summary"] and "DONE" not in r["summary"].split("\n")[0]


def test_asked_notes_close_the_reply_as_observations(tmp_path):
    rt, out = _rt(tmp_path)
    r = rt.call("render_mix", {"wait": 10, "notes": True}, Who.agent("t"))[0]
    assert r["ok"] and out.exists()
    assert r["summary"].split("\n")[-1].startswith("Notes (1): [loudness] -16.9 LUFS") and "fix" not in r["summary"]
    assert r["notes"][0] == {"id": "loudness", "what": "-16.9 LUFS, the master's target is -14", "when": "whole song"}


def test_a_flood_of_alike_notes_stays_one_short_line():
    from rostrum_core.mcp.faults import lines
    many = [note(f"text_on_text:t{i}", "text 't' crosses text 'u'") for i in range(1000)] + [LOUD]
    line = lines(many)
    assert line.startswith("Notes (1001):") and "and 997 more text_on_text" in line and "[loudness]" in line
    assert len(line) < 400
