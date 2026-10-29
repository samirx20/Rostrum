"""Rostrum never refuses or changes an agent's work (Sam, 2026-10-29): a whole-film export with a text cut by the edge
is written under its own name; its checks run only on `notes: true` and close the reply as observations, never fixes."""
from rostrum_core import Who

from rostrum2d.mcp import film_faults, make_app
from rostrum2d.mcp.server import make_runtime

AGENT = Who.agent("tester")
SCENE = ('comp("main", width=320, height=180, fps=10, duration=1, background="#101010")\n'
         'text("title", body="LAUNCH", size=60, x=300, y=90)\n')


def _export(tmp_path, **more):
    rt = make_runtime(make_app(str(tmp_path), ["demo"]))
    rt.call("run_script", {"source": SCENE, "name": "s.py"}, AGENT)
    out = tmp_path / "Launch.gif"
    reply, _ = rt.call("render_export", {"format": "gif", "path": str(out), "overwrite": True, "wait_s": 60, **more}, AGENT)
    while (reply.get("data") or {}).get("status") not in (None, "done", "failed"):
        reply, _ = rt.call("inspect_job", {"job_id": reply["data"]["job_id"], "wait_s": 25}, AGENT)
    return reply, out


def test_a_whole_film_with_a_cut_title_is_written_and_says_nothing_unasked(tmp_path):
    reply, out = _export(tmp_path)
    assert reply["ok"] and out.is_file() and not list(tmp_path.glob("*NOT-DONE*")), reply
    assert "notes" not in reply and "DONE" not in reply["summary"] and "fix" not in reply["summary"].lower()


def test_asked_notes_measure_the_cut_title_without_instructions(tmp_path):
    reply, out = _export(tmp_path, notes=True)
    assert reply["ok"] and out.is_file(), reply
    assert any(n["id"].endswith(":title") for n in reply["notes"]), reply["notes"]
    assert all(set(n) == {"id", "what", "when"} for n in reply["notes"])


def test_scenery_bleeding_off_the_edge_is_not_noted_a_card_is():
    shape_cut = {"kind": "edge_cut", "type": "shape", "start": 0, "end": 10, "id": "reef3", "text": "reef3 cut"}
    card_cut = {**shape_cut, "type": "group", "id": "card"}
    passing = {**card_cut, "end": 1}
    assert [n["id"] for n in film_faults.as_notes([shape_cut, card_cut, passing])] == ["edge_cut:card"]
