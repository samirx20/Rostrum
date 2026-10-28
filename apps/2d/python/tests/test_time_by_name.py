"""Time by name in a 2D script (script_time.py): start="#m+0.5" keeps the agent's numbers and follows the marker;
marker() publishes a shared marker and a re-run without it removes it; stagger / after / beats(bpm=) values."""
import pytest
from rostrum_core import Document, RostrumError, markers as M
from rostrum_core.who import Who

from rostrum2d import KIND, retime
from rostrum2d.script import run_source


def _doc(folder):
    d = Document.new(KIND)
    d.folder = folder
    return d


def _run(doc, body, name="film.py"):
    root = run_source('comp("main", duration=10)\n' + body, name, doc)
    return {n["id"]: n for n in root["comps"][0]["layers"]}


def test_start_on_a_marker_keeps_written_seconds_and_follows_a_drag(tmp_path):
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "reveal", "at": 3.0}}], Who.person("sam"))
    layers = _run(_doc(tmp_path), 't = text("t", body="hi", start="#reveal+0.5", end="#reveal+2")\n'
                                  't.key("opacity", {3.5: 0, "#reveal+0.9": 1})\n')
    t = layers["t"]
    assert (t["marker"], t["start"], t["end"]) == ("reveal", 0.5, pytest.approx(2.0))
    assert [k["t"] for k in t["keys"]] == [pytest.approx(0.5), "#reveal+0.9"]     # stored counted from the marker
    comp = {"id": "main", "type": "comp", "fps": 30, "layers": [t]}
    played = retime.timed(comp, {"reveal": 3.0}, 30)["layers"][0]
    assert played["start"] == 3.5 and [k["t"] for k in played["keys"]] == [3.5, pytest.approx(3.9)]   # as written
    dragged = retime.timed(comp, {"reveal": 5.0}, 30)["layers"][0]
    assert dragged["start"] == 5.5 and [k["t"] for k in dragged["keys"]] == [5.5, pytest.approx(5.9)]


def test_a_missing_marker_fails_naming_the_known_ones(tmp_path):
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "drop", "at": 2.0}}], Who.person("sam"))
    with pytest.raises(RostrumError) as err:
        _run(_doc(tmp_path), 'text("t", body="x", start="#reveal")\n')
    assert "reveal" in str(err.value.to_dict()) and "drop" in str(err.value.to_dict())


def test_marker_publishes_moves_and_a_rerun_without_it_removes_only_its_own(tmp_path):
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "person", "at": 1.0}}], Who.person("sam"))
    doc = _doc(tmp_path)
    _run(doc, 'r = marker("reveal", 3)\nmarker("out", r + 4)\ntext("t", body="x", start=r)\n')
    assert {m["name"]: m["at"] for m in M.listing(tmp_path)} == {"person": 1.0, "reveal": 3.0, "out": 7.0}
    _run(doc, 'marker("reveal", 4)\n')
    assert {m["name"]: m["at"] for m in M.listing(tmp_path)} == {"person": 1.0, "reveal": 4.0}
    _run(doc, 'text("t", body="x")\n')
    assert {m["name"] for m in M.listing(tmp_path)} == {"person"}
    with pytest.raises(RostrumError):                       # a person's marker of that name at another time
        _run(doc, 'marker("person", 2)\n')


def test_stagger_after_and_beats_without_a_song(tmp_path):
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "in", "at": 2.0}}], Who.person("sam"))
    _run(_doc(tmp_path), '''
cards = [shape(f"c{i}") for i in range(3)]
got = [t for t, c in stagger(cards, every=0.5, start="#in")]
assert got == ["#in", "#in+0.5", "#in+1"], got
assert got[1] + 0.4 == "#in+0.9" and 0.4 + got[2] == "#in+1.4"
assert [t for t, c in stagger(cards, every=0.1, start=1)] == [1.0, 1.1, 1.2]
cards[0].key("y", {got[0]: 900, got[0] + 0.4: 700})
assert after(cards[0], gap=0.2) == "#in+0.6", after(cards[0], 0.2)
cards[1].key("y", {1: 0, 2.5: 1})
assert after(cards[1], 0.5) == 3.0
assert beats(bpm=120, count=4) == [0.0, 0.5, 1.0, 1.5]
assert beats(bpm=120, start="#in", count=3) == ["#in", "#in+0.5", "#in+1"]
assert len(beats(bpm=60, start=8)) == 3
''')
