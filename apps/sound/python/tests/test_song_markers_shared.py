"""One marker namespace (AGENTS.md rule 8; 2D final critic F7-2): a song's own markers are seen by 2D by name; the same
name as a project marker at the same time is one marker (never a "damaged" song); at another time it is refused when
it is made, and an export's check says so before a frame is drawn."""
import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_core import markers as M
from rostrum_core import marker_times, song_markers

from rostrum_sound import KIND
from rostrum_sound.doc import markers as own

AGENT = Who.agent("tester")


def _song(folder):
    d = Document.new(KIND, folder=str(folder), item="song")
    d.apply([{"op": "marker.add", "args": {"name": "s2", "at": 4.0}},
             {"op": "marker.add", "args": {"name": "drop", "at": {"beat": 16}}}], AGENT)     # 8 s at 120 bpm
    d.save()
    return d


def test_song_markers_are_seen_by_name_and_a_same_time_twin_is_one_marker(tmp_path):
    d = _song(tmp_path)
    assert M.times(tmp_path) == {"s2": 4.0, "drop": 8.0}
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "S2", "at": 4.0}}], AGENT)      # the same marker: fine
    assert M.lookup(M.times(tmp_path), "s2") == 4.0
    with own.project(str(tmp_path)):
        assert [n for n, _ in own.items(d.data)].count("s2") + [n for n, _ in own.items(d.data)].count("S2") == 1
    song_markers.check(tmp_path, marker_times._project_times(tmp_path), "export")     # nothing to say


def test_a_name_at_another_time_is_refused_when_made(tmp_path):
    _song(tmp_path)
    with pytest.raises(RostrumError, match="already has its own marker"):
        M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "drop", "at": 9.0}}], AGENT)
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "hit", "at": 2.0}}], AGENT)
    hit = M.listing(tmp_path)[0]["id"]
    with pytest.raises(RostrumError, match="already has its own marker"):
        M.edit(tmp_path, [{"op": "marker.rename", "target": [hit], "args": {"name": "s2"}}], AGENT)
