"""Moving a cut moves its lead-in (doc/ops_carry.py): what starts just before a marker is re-timed onto it, plays at
the same moment, follows the marker when it moves, and undo is exact; what would stay behind is named, never moved
silently. Without this a riser written on another marker ends before the picture cut."""
from rostrum_core import Document, Who
from rostrum_core import markers as project

from rostrum_sound import KIND, compile
from rostrum_sound.doc import markers, ops_carry
from rostrum_sound.mcp import tools_notes

P = Who.person()


def _song(tmp_path):
    project.edit(tmp_path, [{"op": "marker.add", "args": {"name": "tense", "at": 10.0}},
                            {"op": "marker.add", "args": {"name": "reveal", "at": 20.0}}], P)
    d = Document.new(KIND, folder=tmp_path, item="cue")
    add = lambda i, at, dur=1.0: {"op": "note.add", "target": ["s"], "args": {"id": i, "pitch": "C4", "at": at, "dur": dur}}  # noqa: E731
    d.apply([{"op": "track.add", "target": [], "args": {"id": "s", "instrument": "builtIn", "builtIn": "piano"}},
             add("riser", "#tense+8.5", 1.5), add("tail", 16.0, 3.9), add("early", 5.0), add("hold", "#reveal", 2.0)], P)
    return d


def _starts(d):
    return {n["id"]: round(markers.seconds_of(d.data, n["at"]), 4) for n in d.item("s")["notes"]}


def test_a_carried_lead_in_follows_the_marker_and_undo_is_exact(tmp_path):
    with markers.project(tmp_path):
        d = _song(tmp_path)
        before = _starts(d)
        assert "2 notes on s " in ops_carry.staying_words(d.data, "reveal")    # riser and tail end just before the cut
        d.apply([{"op": "marker.carry", "args": {"marker": "reveal", "lead_in": 4}}], P)
        assert _starts(d) == before                                         # same moment
        ids = {n["id"]: n["at"] for n in d.item("s")["notes"]}
        assert ids["riser"] == "#reveal-1.5" and ids["tail"] == "#reveal-4" and ids["early"] == 5.0 and ids["hold"] == "#reveal"
        project.edit(tmp_path, [{"op": "marker.move", "target": [project.listing(tmp_path)[1]["id"]], "args": {"at": 26.0}}], P)
        now = _starts(d)
        assert now["riser"] == 24.5 and now["tail"] == 22.0 and now["early"] == 5.0
        d.undo(P)
        assert d.item("s")["notes"][0]["at"] == "#tense+8.5"


def test_notes_listing_is_compact_and_capped(tmp_path):
    with markers.project(tmp_path):
        d = _song(tmp_path)
        rows = tools_notes._line(d.data, "note", d.item("riser"))
        assert rows.startswith("riser  18.50 s  bar ") and "C4" in rows


def test_edit_markers_carries_with_lead_in_and_warns_without(tmp_path, monkeypatch):
    from test_mcp_project_sound import AGENT, start
    (tmp_path / "p").mkdir()
    project.edit(tmp_path / "p", [{"op": "marker.add", "args": {"name": "reveal", "at": 20.0}}], P)
    d = Document.new(KIND, folder=str(tmp_path / "p"), item="cue")
    d.apply([{"op": "track.add", "target": [], "args": {"id": "s", "instrument": "builtIn", "builtIn": "piano"}},
             {"op": "note.add", "target": ["s"], "args": {"id": "rise", "pitch": "C4", "at": 17.0, "dur": 3.0}}], P)
    d.save()
    app, rt = start(tmp_path, monkeypatch, [{"folder": str(tmp_path / "p"), "item": "cue", "name": "p"}])
    try:
        move = lambda args: rt.call("edit_markers", {"ops": [{"op": "marker.move", "target": ["reveal"], "args": args}]}, AGENT)[0]  # noqa: E731
        listed = rt.call("inspect_notes", {"track": "s", "from": "#reveal-4"}, AGENT)[0]
        assert listed["ok"] and "rise  17 s" in listed["summary"].replace(".00", "")
        warned = move({"at": 25.0})
        assert any("1 note on s end just before #reveal" in w for w in warned["warnings"]), warned
        move({"at": 20.0})                                                  # back where it was
        moved = move({"at": 26.0, "lead_in": 4})
        assert moved["ok"] and app.documents["cue"].item("rise")["at"] == "#reveal-3"
        assert round(markers.seconds_of(app.documents["cue"].data, "#reveal-3"), 3) == 23.0                # 17 + 6: it went with the cut
    finally:
        app.state.engine.close()
